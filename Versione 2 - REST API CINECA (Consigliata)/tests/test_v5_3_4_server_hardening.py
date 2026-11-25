"""v5.3.4: Server hardening HTTP, semaforo 40 slot e timeout 15s (ST-08), login atomico (ST-10.3), whitelist /api/admin/save (N-10)."""
import json
import socket
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests._harness import avvia_http, carica_server, chiudi_server, ferma_http, login_admin, richiesta


class TestServerHardening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def setUp(self):
        with self.srv.lock_login:
            self.srv.LOGIN_ATTEMPTS.clear()

    def test_timeout_socket_handler_15s_e_semaforo_40_st08(self):
        self.assertEqual(self.srv.KioskServer.timeout, 15.0)
        self.assertEqual(self.srv.MAX_CONCURRENT_REQUESTS, 40)
        self.assertIsInstance(self.srv.HTTP_CONCURRENCY_SEMAPHORE, threading.BoundedSemaphore)

        porta = self.httpd.server_address[1]
        with socket.create_connection(('127.0.0.1', porta), timeout=5) as sock:
            sock.sendall(b'GET /stato HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
            risposta = b''
            while True:
                pezzo = sock.recv(4096)
                if not pezzo:
                    break
                risposta += pezzo
        self.assertIn(b'200 OK', risposta)

        acquisiti = 0
        try:
            while self.srv.HTTP_CONCURRENCY_SEMAPHORE.acquire(blocking=False):
                acquisiti += 1
            self.assertEqual(acquisiti, 40)

            status, headers, corpo = richiesta(self.base + '/stato')
            self.assertEqual(status, 503)
            headers_lower = {k.lower(): v for k, v in headers.items()}
            self.assertEqual(headers_lower.get('retry-after'), '5')
            self.assertIn('application/json', headers_lower.get('content-type', '').lower())
            dati_err = json.loads(corpo.decode('utf-8'))
            self.assertIs(dati_err.get('success'), False)
            self.assertIn('error', dati_err)
        finally:
            for _ in range(acquisiti):
                self.srv.HTTP_CONCURRENCY_SEMAPHORE.release()

        status_ok, _, _ = richiesta(self.base + '/stato')
        self.assertEqual(status_ok, 200)

    def test_login_check_and_increment_atomico_concorrente_st10_3(self):
        self.srv.CONFIG['sicurezza'].update({
            'admin_attivo': True,
            'admin_ip_autorizzati': [],
            'password_admin_hash': 'a' * 64,
        })

        def tenta_login(_idx):
            s, headers, corpo = richiesta(
                self.base + '/api/admin/login',
                'POST',
                json.dumps({'password': 'password-sbagliata'}).encode('utf-8'),
                {'Content-Type': 'application/json'},
            )
            return s, {k.lower(): v for k, v in headers.items()}.get('retry-after'), corpo

        with ThreadPoolExecutor(max_workers=15) as pool:
            risultati = list(pool.map(tenta_login, range(15)))

        codici = [r[0] for r in risultati]
        self.assertEqual(codici.count(401), 5, f'Attesi esattamente 5 HTTP 401 prima del blocco, ottenuti: {codici}')
        self.assertEqual(codici.count(429), 10, f'Attesi esattamente 10 HTTP 429 atomici, ottenuti: {codici}')
        self.assertEqual(self.srv.LOGIN_ATTEMPTS['127.0.0.1']['count'], 5)

        risposte_429 = [r for r in risultati if r[0] == 429]
        self.assertTrue(all(r[1] is not None and int(r[1]) > 0 for r in risposte_429))
        dati_429 = json.loads(risposte_429[0][2].decode('utf-8'))
        self.assertIn('secondi_attesa', dati_429)
        self.assertGreater(dati_429['secondi_attesa'], 0)

    def test_whitelist_admin_save_rifiuta_chiavi_e_path_ostili_n10(self):
        token = login_admin(self.srv, self.base)
        headers = {'Content-Type': 'application/json', 'X-Admin-Token': token}

        casi_ostili = [
            {'sezione_ignota': {'x': 1}},
            {'main': {'chiave_arbitraria': 'valore'}},
            {'main': {'file_log': '/home/pi/.xinitrc'}},
            {'main': {'file_log': '../../etc/cron.d/pwn.log'}},
            {'main': {'percorso_base': '/etc'}},
            {'main': {'porta_server': 70000}},
            {'https': {'file_certificato': '../../../etc/ssl/private.key'}},
            {'https': {'file_chiave': '/etc/shadow'}},
            {'footer_news': {'fonti': [{'nome': 'Test', 'url': 'https://a.it', 'comando_shell': 'id'}]}},
        ]

        for payload in casi_ostili:
            status, _, corpo = richiesta(
                self.base + '/api/admin/save',
                'POST',
                json.dumps(payload).encode('utf-8'),
                headers,
            )
            self.assertEqual(status, 400, f'Payload ostile non rifiutato: {payload} -> {corpo}')

        # Verifica compatibilita' col payload completo reale inviato da admin.html (...currentConfig.main, porta_server str, colore_btn)
        status_cfg, _, corpo_cfg = richiesta(self.base + '/api/admin/config_full', 'GET', header=headers)
        self.assertEqual(status_cfg, 200)
        current_cfg = json.loads(corpo_cfg.decode('utf-8'))

        payload_browser_admin = {
            'main': {
                **current_cfg['main'],
                'porta_server': str(current_cfg['main'].get('porta_server', '8080')),
                'debug_mode': False,
            },
            'frontend': {
                **current_cfg['frontend'],
                'titoloSede': 'Polo Ingegneria',
            },
            'footer_news': {
                **current_cfg['footer_news'],
                'colore_btn': '#30363d',
            },
        }
        status_ok, _, corpo_ok = richiesta(
            self.base + '/api/admin/save',
            'POST',
            json.dumps(payload_browser_admin).encode('utf-8'),
            headers,
        )
        self.assertEqual(status_ok, 200, corpo_ok)
        self.assertEqual(self.srv.CONFIG['frontend']['titoloSede'], 'Polo Ingegneria')
        self.assertEqual(self.srv.CONFIG['main']['porta_server'], 8080)


if __name__ == '__main__':
    unittest.main()
