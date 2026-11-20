"""v5.2.5: endpoint /stato, classificazione In corso lato client, badge di freschezza CINECA."""
import json
import time
import unittest

from tests._harness import avvia_http, carica_server, chiudi_server, evento, ferma_http, richiesta
from tests._harness_js import NODE, esegui_js, leggi_pagina


class TestStato(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def stato(self):
        status, _, corpo = richiesta(self.base + '/stato')
        self.assertEqual(status, 200)
        return json.loads(corpo)

    def test_campi_e_tipi(self):
        s = self.stato()
        self.assertEqual(set(s), {'ultimo_sync_cineca', 'preservato', 'ora_server', 'avvio_server', 'intervallo_sec'})
        self.assertIsInstance(s['preservato'], bool)
        self.assertIsInstance(s['intervallo_sec'], int)
        self.assertLess(abs(s['ora_server'] - time.time()), 5)

    def test_sync_riuscito_registrato(self):
        self.srv.CONFIG.setdefault('api_cineca', {})['id_edificio'] = '05'
        self.srv.elabora_risposta_cineca([evento('E1')])
        s = self.stato()
        self.assertIsNotNone(s['ultimo_sync_cineca'])
        self.assertEqual([imp['id'] for imp in json.loads(richiesta(self.base + '/dati.json')[2])], ['E1'])

    def test_tabellone_non_viene_piu_cancellato(self):
        html = leggi_pagina('remoto.html')
        self.assertNotIn('erroriConsecutivi >= 4', html)
        self.assertRegex(html, r"fetch\(['\"]\.?/stato")


@unittest.skipUnless(NODE, 'Node.js non disponibile')
class TestFunzioniPure(unittest.TestCase):

    def test_classificazione(self):
        dati = ('[{id:"a",timestamp_inizio:100,timestamp_fine:200},{id:"b",timestamp_inizio:300,timestamp_fine:400},'
                '{id:"c",timestamp_inizio:0,timestamp_fine:50}]')
        r = esegui_js('remoto.html', ['classificaImpegni'], f'classificaImpegni({dati}, 150)')
        self.assertEqual([i['id'] for i in r['inCorso']], ['a'])
        self.assertTrue(r['inCorso'][0]['inCorso'])
        self.assertEqual([i['id'] for i in r['futuri']], ['b'])

    def freschezza(self, stato, adesso):
        return esegui_js('remoto.html', ['valutaFreschezza'], f'valutaFreschezza({stato}, {adesso})')

    def test_dati_freschi(self):
        self.assertFalse(self.freschezza('{ultimo_sync_cineca:1000,intervallo_sec:300,avvio_server:0}', 1600)['mostra'])

    def test_dati_vecchi(self):
        r = self.freschezza('{ultimo_sync_cineca:1000,intervallo_sec:300,avvio_server:0}', 2000)
        self.assertTrue(r['mostra'])
        self.assertRegex(r['testo'], r'\d{2}:\d{2}')

    def test_soglia_cresce_con_intervallo(self):
        self.assertFalse(self.freschezza('{ultimo_sync_cineca:1000,intervallo_sec:600,avvio_server:0}', 2000)['mostra'])

    def test_mai_sincronizzato(self):
        self.assertTrue(self.freschezza('{ultimo_sync_cineca:null,intervallo_sec:300,avvio_server:0}', 700)['mostra'])
        self.assertFalse(self.freschezza('{ultimo_sync_cineca:null,intervallo_sec:300,avvio_server:0}', 60)['mostra'])


if __name__ == '__main__':
    unittest.main()
