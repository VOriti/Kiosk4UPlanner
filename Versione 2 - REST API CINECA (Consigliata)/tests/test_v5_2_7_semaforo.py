"""v5.2.7: diagnostica per fonte esposta solo all'admin."""
import json
import unittest
from unittest import mock

import requests

from tests._harness import avvia_http, carica_server, chiudi_server, ferma_http, login_admin, richiesta

OK, NON_TROVATA, LENTA, ROTTA, SPENTA = (f'https://{n}.test/rss' for n in ('ok', 'nf', 'lenta', 'rotta', 'spenta'))


class Risposta:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def get_finto(url, timeout):
    if url == OK:
        return Risposta(b'<rss><channel><item><title>Uno</title></item><item><title>Due</title></item></channel></rss>')
    if url == NON_TROVATA:
        return Risposta(b'', status=404)
    if url == LENTA:
        raise requests.exceptions.Timeout()
    return Risposta(b'<rss><channel><item>')


class TestSemaforo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)
        cls.token = login_admin(cls.srv, cls.base)
        fonti = [{'nome': n, 'url': u, 'tipo': 'rss', 'abilitata': u != SPENTA, 'peso': 1}
                 for n, u in (('Ok', OK), ('Nf', NON_TROVATA), ('Lenta', LENTA), ('Rotta', ROTTA), ('Spenta', SPENTA))]
        fonti.append({'nome': '', 'url': '', 'tipo': 'rss', 'abilitata': False, 'peso': 1})
        cls.srv.CONFIG['footer_news'] = {'abilitato': True, 'fonti': fonti}
        with mock.patch.object(cls.srv.requests, 'get', side_effect=get_finto):
            cls.srv.aggiorna_news_una_volta()

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def test_stati_per_fonte(self):
        d = self.srv.DIAGNOSTICA_NEWS
        self.assertEqual((d[OK]['stato'], d[OK]['articoli']), ('OK', 2))
        self.assertRegex(d[OK]['ora'], r'^\d{2}:\d{2}$')
        self.assertEqual(d[NON_TROVATA]['stato'], 'HTTP 404')
        self.assertEqual(d[LENTA]['stato'], 'Timeout')
        self.assertEqual(d[ROTTA]['stato'], 'Errore formato XML')
        self.assertEqual(d[SPENTA]['stato'], 'DISABILITATA')
        self.assertNotIn('', d)

    def test_esposta_solo_all_admin(self):
        status, _, corpo = richiesta(self.base + '/api/admin/config_full', header={'X-Admin-Token': self.token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(corpo)['diagnostica_news'][NON_TROVATA]['stato'], 'HTTP 404')
        pubblico = richiesta(self.base + '/api/news')[2].decode('utf-8')
        self.assertNotIn('HTTP 404', pubblico)
        self.assertTrue(all('stato' not in n for n in json.loads(pubblico)))

    def test_admin_mostra_il_semaforo(self):
        with open(self.srv._tmpdir + '/admin.html', encoding='utf-8') as f:
            self.assertIn('diagnostica_news', f.read())


if __name__ == '__main__':
    unittest.main()
