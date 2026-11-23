"""v5.3.1: CinecaClient, backoff esponenziale (N-05), timeout 15s, sentinella 500 e motore D-01."""
import datetime
import os
import sys
import time
import unittest
from unittest import mock

import requests

from tests._harness import DIR_APP, carica_server, chiudi_server, evento, per_id

if DIR_APP not in sys.path:
    sys.path.insert(0, DIR_APP)

from core.cineca_client import (
    AVVISI_DI_STATO,
    LIMITE_EVENTI_CINECA,
    SOGLIA_ASSENZE_ANNULLAMENTO,
    CinecaClient,
)


class RispostaFintaCineca:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)


class TestCinecaClientBackoff(unittest.TestCase):

    def setUp(self):
        self.client = CinecaClient(
            url_base='https://mock.cineca.it/api/',
            realm='unipv_test',
            username='utente_kiosk',
            password='segreta',
            timeout=15,
            usa_jitter=False,
        )

    def test_costanti_e_inizializzazione(self):
        self.assertEqual(self.client.url_base, 'https://mock.cineca.it/api')
        self.assertEqual(self.client.timeout, 15.0)
        self.assertEqual(LIMITE_EVENTI_CINECA, 500)
        self.assertEqual(SOGLIA_ASSENZE_ANNULLAMENTO, 2)
        self.assertEqual(AVVISI_DI_STATO, ('ANNULLATO', 'SOSPESO'))
        self.assertEqual(self.client.fallimenti_consecutivi, 0)
        self.assertEqual(self.client.prossimo_tentativo_login, 0.0)
        self.assertIsNone(self.client.token)

    def test_curva_backoff_esponenziale_senza_jitter(self):
        attesi = {1: 120.0, 2: 240.0, 3: 480.0, 4: 960.0, 5: 1920.0, 6: 3600.0, 10: 3600.0}
        for n, atteso in attesi.items():
            self.assertEqual(self.client.calcola_backoff(n), atteso)

    def test_backoff_con_jitter_limitato(self):
        client_jitter = CinecaClient('https://mock.cineca.it/api', 'r', 'u', 'p', usa_jitter=True)
        for _ in range(20):
            b1 = client_jitter.calcola_backoff(1)
            self.assertGreaterEqual(b1, 120.0)
            self.assertLessEqual(b1, 132.0)
            b6 = client_jitter.calcola_backoff(6)
            self.assertGreaterEqual(b6, 3600.0)
            self.assertLessEqual(b6, 3600.0)

    @mock.patch('core.cineca_client.requests.post')
    def test_login_fallito_attiva_backoff_e_salta_chiamate_in_finestra(self, mock_post):
        mock_post.return_value = RispostaFintaCineca(status_code=401)
        t0 = 10000.0
        token = self.client.login(now=t0)
        self.assertIsNone(token)
        self.assertEqual(self.client.fallimenti_consecutivi, 1)
        self.assertEqual(mock_post.call_args.kwargs['timeout'], 15.0)
        self.assertFalse(self.client.puo_tentare_login(now=t0 + 60.0))

        mock_post.reset_mock()
        token_bloccato = self.client.login(now=t0 + 60.0)
        self.assertIsNone(token_bloccato)
        mock_post.assert_not_called()

        token_2 = self.client.login(now=t0 + 121.0)
        self.assertIsNone(token_2)
        self.assertEqual(self.client.fallimenti_consecutivi, 2)
        self.assertAlmostEqual(self.client.ultimo_backoff_applicato, 240.0)

    @mock.patch('core.cineca_client.requests.post')
    def test_login_timeout_incrementa_backoff(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout('Read timed out')
        token = self.client.login(now=5000.0)
        self.assertIsNone(token)
        self.assertEqual(self.client.fallimenti_consecutivi, 1)
        self.assertGreater(self.client.prossimo_tentativo_login, 5000.0)

    @mock.patch('core.cineca_client.requests.post')
    def test_login_riuscito_azzera_backoff(self, mock_post):
        self.client.fallimenti_consecutivi = 5
        self.client.prossimo_tentativo_login = 0.0
        mock_post.return_value = RispostaFintaCineca(status_code=200, payload={'id': 'tok-abc-123'})

        token = self.client.login(now=20000.0)
        self.assertEqual(token, 'tok-abc-123')
        self.assertEqual(self.client.token, 'tok-abc-123')
        self.assertEqual(self.client.fallimenti_consecutivi, 0)
        self.assertEqual(self.client.prossimo_tentativo_login, 0.0)

    @mock.patch('core.cineca_client.requests.post')
    def test_fetch_impegni_timeout_15s_e_401_invalida_token(self, mock_post):
        self.client.token = 'tok-vecchio'
        mock_post.return_value = RispostaFintaCineca(status_code=401)
        esito = self.client.fetch_impegni(datetime.date(2026, 11, 23), anno_accademico_id='2026', contesto_id='C1')
        self.assertIsNone(esito)
        self.assertIsNone(self.client.token)
        self.assertEqual(mock_post.call_args.kwargs['timeout'], 15.0)
        payload_inviato = mock_post.call_args.kwargs['json']
        self.assertEqual(payload_inviato['limit'], 500)
        self.assertEqual(payload_inviato['annoAccademicoId'], '2026')
        self.assertEqual(payload_inviato['contestoId'], 'C1')

    def test_sentinella_limite_500_e_motore_d01_diretto(self):
        with self.assertLogs(level='WARNING') as log:
            self.assertTrue(self.client.verifica_sentinella_limite([{'id': i} for i in range(500)]))
        self.assertTrue(any('SENTINELLA LIMITE CINECA' in r for r in log.output))
        self.assertFalse(self.client.verifica_sentinella_limite([{'id': i} for i in range(499)]))

        storico = {}
        e1 = evento('A1', edificio='05')
        e2 = evento('A2', edificio='05')
        dati, pres = CinecaClient.processa_impegni([e1, e2], storico, id_edificio='05', mostra_confermati=True)
        self.assertFalse(pres)
        self.assertEqual(len(dati), 2)

        dati_c1, _ = CinecaClient.processa_impegni([e1], storico, id_edificio='05', mostra_confermati=True)
        mappa_c1 = per_id(dati_c1)
        self.assertFalse(mappa_c1['A2']['cancellato'])
        self.assertEqual(mappa_c1['A2']['assenze'], 1)

        dati_c2, _ = CinecaClient.processa_impegni([e1], storico, id_edificio='05', mostra_confermati=True)
        mappa_c2 = per_id(dati_c2)
        self.assertTrue(mappa_c2['A2']['cancellato'])
        self.assertEqual(mappa_c2['A2']['avviso'], 'ANNULLATO')

        dati_heal, _ = CinecaClient.processa_impegni([e1, e2], storico, id_edificio='05', mostra_confermati=True)
        mappa_heal = per_id(dati_heal)
        self.assertFalse(mappa_heal['A2']['cancellato'])
        self.assertEqual(mappa_heal['A2']['avviso'], '')


class TestIntegrazioneHarnessCore(unittest.TestCase):

    def test_harness_carica_core_isolato(self):
        srv = carica_server()
        try:
            self.assertTrue(os.path.isdir(os.path.join(srv._tmpdir, 'core')))
            self.assertTrue(os.path.isfile(os.path.join(srv._tmpdir, 'core', 'cineca_client.py')))
            srv.CONFIG.setdefault('api_cineca', {})['id_edificio'] = '05'
            out = per_id(srv.estrai_e_formatta_dati([evento('H1', edificio='05')]))
            self.assertIn('H1', out)
            self.assertFalse(out['H1']['cancellato'])
        finally:
            chiudi_server(srv)


if __name__ == '__main__':
    unittest.main()
