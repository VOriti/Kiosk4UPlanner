"""v5.3.6: Audit paginazione CINECA UP (POST), validazione salvaguardia contesto/anno e regressione contratti D-05."""
import datetime
import json
import os
import sys
import unittest
from unittest import mock

import requests

from tests._harness import DIR_APP, avvia_http, carica_server, chiudi_server, ferma_http, login_admin, richiesta

if DIR_APP not in sys.path:
    sys.path.insert(0, DIR_APP)

from core.cineca_client import CinecaClient


class RispostaSondaFinta:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)


class TestAuditPaginazioneCINECA(unittest.TestCase):

    def setUp(self):
        self.client = CinecaClient('https://mock.cineca.it/api', 'Realm', 'usr', 'pwd')
        self.client.token = 'tok-valido'
        self.giorno = datetime.date(2026, 11, 23)

    @mock.patch('core.cineca_client.requests.post')
    def test_sonda_rileva_paginazione_non_supportata(self, mock_post):
        # CINECA UP ignora skip/offset/page e restituisce sempre gli stessi ID
        mock_post.return_value = RispostaSondaFinta(
            status_code=200,
            payload=[{'id': 'E1'}, {'id': 'E2'}, {'id': 'E3'}, {'id': 'E4'}, {'id': 'E5'}],
        )
        esito = self.client.verifica_supporto_paginazione(self.giorno)
        self.assertFalse(esito['supportata'])
        self.assertIsNone(esito['parametro'])

    @mock.patch('core.cineca_client.requests.post')
    def test_sonda_rileva_paginazione_skip_supportata(self, mock_post):
        def finta_post(url, json=None, headers=None, timeout=15):
            if json.get('skip', 0) == 0:
                return RispostaSondaFinta(200, [{'id': f'E{i}'} for i in range(1, 6)])
            return RispostaSondaFinta(200, [{'id': f'E{i}'} for i in range(6, 11)])

        mock_post.side_effect = finta_post
        esito = self.client.verifica_supporto_paginazione(self.giorno)
        self.assertTrue(esito['supportata'])
        self.assertEqual(esito['parametro'], 'skip')

    def test_validazione_configurazione_salvaguardia(self):
        self.assertFalse(CinecaClient.valida_configurazione_salvaguardia({'api_cineca': {'id_edificio': '05'}}))
        self.assertFalse(CinecaClient.valida_configurazione_salvaguardia({
            'api_cineca': {'anno_accademico_id': '2026', 'contesto_id': ''},
        }))
        self.assertFalse(CinecaClient.valida_configurazione_salvaguardia({
            'api_cineca': {'anno_accademico_id': '2026', 'contesto_id': 'ab'},
        }))
        self.assertFalse(CinecaClient.valida_configurazione_salvaguardia({
            'api_cineca': {'anno_accademico_id': '2026', 'contesto_id': 'testo a caso!'},
        }))
        self.assertTrue(CinecaClient.valida_configurazione_salvaguardia({
            'api_cineca': {'anno_accademico_id': '2026', 'contesto_id': 'CTX01', 'id_edificio': '05'},
        }))
        self.assertTrue(CinecaClient.valida_configurazione_salvaguardia({
            'api_cineca': {
                'anno_accademico_id': '5e1553cac831d600172af6d0',
                'contesto_id': '5b97788424deec000e171a8f',
                'id_edificio': '05',
            },
        }))

    @mock.patch('core.cineca_client.requests.get')
    def test_scopri_anagrafiche_debug_anni_e_contesti(self, mock_get):
        def finta_get(url, headers=None, timeout=15):
            if url.endswith('/AnniAccademici'):
                return RispostaSondaFinta(200, [
                    {
                        'id': '5fefefdef4653b001808e636',
                        'codice': '2026',
                        'descrizione': '2026/2027',
                        'dataInizio': '2020-01-01T00:00:00.000Z',
                        'dataFine': '2035-12-31T23:59:59.000Z',
                    },
                ])
            if url.endswith('/Contesti'):
                return RispostaSondaFinta(200, [
                    {
                        'id': '5b97788424deec000e171a8f',
                        'codice': 'Polo A',
                        'descrizione': 'Polo Centrale',
                    },
                ])
            return RispostaSondaFinta(404, [])

        mock_get.side_effect = finta_get
        with self.assertLogs(level='INFO') as cm:
            esito = self.client.scopri_anagrafiche_debug(
                anno_accademico_id='5fefefdef4653b001808e636',
                contesto_id='5b97788424deec000e171a8f',
            )
        self.assertEqual(len(esito['anni_accademici']), 1)
        self.assertEqual(len(esito['contesti']), 1)
        log_unito = '\n'.join(cm.output)
        self.assertIn('DEBUG MAPPA ANNI ACCADEMICI RILEVATI', log_unito)
        self.assertIn('ANNO IN CORSO', log_unito)
        self.assertIn('DEBUG MAPPA CONTESTI RILEVATI', log_unito)
        self.assertIn('Polo Centrale', log_unito)


class TestRegressioneContrattiESalvaguardia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server(con_locandine=True)
        cls.base, cls.httpd = avvia_http(cls.srv)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def test_contratti_pubblici_d05_invariati(self):
        for endpoint, tipo_atteso in (
            ('/dati.json', list),
            ('/lista_locandine.json', list),
            ('/api/news', list),
            ('/config_pubblica', dict),
            ('/stato', dict),
        ):
            status, headers, corpo = richiesta(self.base + endpoint)
            self.assertEqual(status, 200, endpoint)
            ct = {k.lower(): v for k, v in headers.items()}.get('content-type', '')
            self.assertIn('application/json', ct.lower(), endpoint)
            dati = json.loads(corpo.decode('utf-8'))
            self.assertIsInstance(dati, tipo_atteso, endpoint)

    def test_admin_save_impone_filtri_cineca_se_attivo(self):
        token = login_admin(self.srv, self.base)
        headers = {'Content-Type': 'application/json', 'X-Admin-Token': token}

        payload_senza_filtri = {
            'api_cineca': {
                'username': 'utente_reale',
                'password': 'password_reale',
                'anno_accademico_id': '',
                'contesto_id': '',
            }
        }
        status_err, _, corpo_err = richiesta(
            self.base + '/api/admin/save',
            'POST',
            json.dumps(payload_senza_filtri).encode('utf-8'),
            headers,
        )
        self.assertEqual(status_err, 400, corpo_err)

        # In Debug Mode attivo e' consentito salvare temporaneamente senza Anno/Contesto per scoprirne gli ID in kiosk.log
        status_dbg, _, corpo_dbg = richiesta(
            self.base + '/api/admin/save',
            'POST',
            json.dumps({
                'main': {'debug_mode': True},
                **payload_senza_filtri,
            }).encode('utf-8'),
            headers,
        )
        self.assertEqual(status_dbg, 200, corpo_dbg)
        # Disattivando Debug Mode con Anno/Contesto ancora vuoti torna il blocco rigoroso HTTP 400
        status_off, _, _ = richiesta(
            self.base + '/api/admin/save',
            'POST',
            json.dumps({
                'main': {'debug_mode': False},
                **payload_senza_filtri,
            }).encode('utf-8'),
            headers,
        )
        self.assertEqual(status_off, 400)

        for id_invalido in ('abc', 'testo a caso', 'id!non@valido'):
            status_bad_fmt, _, corpo_bad_fmt = richiesta(
                self.base + '/api/admin/save',
                'POST',
                json.dumps({
                    'api_cineca': {
                        'username': 'utente_reale',
                        'password': 'password_reale',
                        'anno_accademico_id': '5e1553cac831d600172af6d0',
                        'contesto_id': id_invalido,
                    }
                }).encode('utf-8'),
                headers,
            )
            self.assertEqual(status_bad_fmt, 400, f'ID invalido accettato: {id_invalido} -> {corpo_bad_fmt}')

        payload_valido = {
            'api_cineca': {
                'username': 'utente_reale',
                'password': 'password_reale',
                'anno_accademico_id': '2026',
                'contesto_id': 'ING01',
                'id_edificio': '05',
            }
        }
        status_ok, _, corpo_ok = richiesta(
            self.base + '/api/admin/save',
            'POST',
            json.dumps(payload_valido).encode('utf-8'),
            headers,
        )
        self.assertEqual(status_ok, 200, corpo_ok)

    def test_box_informativo_cineca_presente_in_admin_html(self):
        with open(os.path.join(DIR_APP, 'admin.html'), encoding='utf-8') as f:
            admin_html = f.read()
        self.assertIn('Come filtrano gli orari Anno Accademico, Contesto ed Edificio', admin_html)
        self.assertIn('ID Contesto — Polo / Dipartimento / Area', admin_html)
        self.assertIn('Promemoria di inizio Anno Accademico', admin_html)

        # Verifica che debug_mode sia posizionato dentro #panel-cineca subito dopo il box guida (prima di #anno_accademico_id e prima di #panel-rete)
        idx_cineca = admin_html.index('id="panel-cineca"')
        idx_box = admin_html.index('Come filtrano gli orari Anno Accademico, Contesto ed Edificio')
        idx_debug = admin_html.index('id="debug_mode"')
        idx_anno = admin_html.index('id="anno_accademico_id"')
        idx_rete = admin_html.index('id="panel-rete"')
        self.assertLess(idx_cineca, idx_box)
        self.assertLess(idx_box, idx_debug)
        self.assertLess(idx_debug, idx_anno)
        self.assertLess(idx_debug, idx_rete)

        # Verifica bordino colorato su tutte e 7 le tendine accordion-panel
        for pid, cls_colore in (
            ('panel-frontend', 'accent-blue'),
            ('panel-alert', 'highlight-warning'),
            ('panel-locandine', 'accent-purple'),
            ('panel-footer', 'accent-teal'),
            ('panel-cineca', 'accent-blue'),
            ('panel-rete', 'accent-orange'),
            ('panel-https', 'accent-green'),
        ):
            self.assertRegex(
                admin_html,
                rf'<div\s+class="accordion-panel\s+{cls_colore}"\s+id="{pid}">',
                f'Bordino mancante su {pid}',
            )

    def test_sandbox_contiene_tutti_moduli_core_e_asset(self):
        for rel in (
            os.path.join('core', '__init__.py'),
            os.path.join('core', 'cineca_client.py'),
            os.path.join('core', 'news_engine.py'),
            os.path.join('core', 'building_context.py'),
            os.path.join('static', 'remoto.js'),
            os.path.join('static', 'remoto.css'),
            os.path.join('static', 'admin.js'),
            os.path.join('static', 'admin.css'),
        ):
            self.assertTrue(os.path.isfile(os.path.join(self.srv._tmpdir, rel)), f'Mancante in sandbox: {rel}')


if __name__ == '__main__':
    unittest.main()
