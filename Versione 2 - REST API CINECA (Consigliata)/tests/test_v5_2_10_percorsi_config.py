"""v5.2.10: percorsi relativi, config.example.yaml, avviso sicurezza password default e guardia url_base."""
import json
import os
import re
import shutil
import subprocess
import unittest

import yaml

from tests._harness import DIR_APP, avvia_http, carica_server, chiudi_server, ferma_http, login_admin, richiesta
from tests._harness_js import NODE, esegui_js, leggi_pagina

RADICE_REPO = os.path.abspath(os.path.join(DIR_APP, '..', '..'))
HASH_ADMIN = '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918'   # sha256("admin")


class TestPercorsi(unittest.TestCase):

    def test_nessun_fetch_assoluto(self):
        html = leggi_pagina('remoto.html')
        self.assertEqual(re.findall(r"fetch\(\s*['\"`]/", html), [])
        for endpoint in ('config_pubblica', 'dati.json', 'api/news', 'lista_locandine.json', 'stato'):
            self.assertRegex(html, r"fetch\(\s*['\"`]\./" + re.escape(endpoint))

    @unittest.skipUnless(NODE, 'Node.js non disponibile')
    def test_url_locandina_relativo(self):
        self.assertEqual(esegui_js('remoto.html', ['urlLocandina'], 'urlLocandina("p1_ab.jpg")'), './locandine/p1_ab.jpg')


class TestConfigurazione(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()

    @classmethod
    def tearDownClass(cls):
        chiudi_server(cls.srv)

    def test_default_aggiornati(self):
        default = yaml.safe_load(self.srv.DEFAULT_CONFIG.replace('{PERCORSO}', '/tmp'))
        self.assertEqual(default['frontend']['urlLogo'], './logo.png')
        self.assertEqual(default['frontend']['intervalloAggiornamento'], 15000)

    def test_example_allineato_al_default(self):
        with open(os.path.join(DIR_APP, 'config.example.yaml'), encoding='utf-8') as f:
            esempio = yaml.safe_load(f)
        default = yaml.safe_load(self.srv.DEFAULT_CONFIG.replace('{PERCORSO}', '/tmp'))
        self.assertEqual(set(esempio), set(default))
        for sezione in default:
            self.assertEqual(set(esempio[sezione]), set(default[sezione]), sezione)
        self.assertEqual((esempio['api_cineca']['username'], esempio['api_cineca']['password']), ('', ''))
        self.assertTrue(esempio['sicurezza']['admin_ip_autorizzati'])

    def test_hash_password_default(self):
        self.assertIn(HASH_ADMIN, self.srv.HASH_PASSWORD_DEFAULT)
        self.assertIn('a45090e56b7639cae365ee553d321fe8ef76300adcab875a064bb3f0abbc08d0', self.srv.HASH_PASSWORD_DEFAULT)
        self.assertNotIn('f' * 64, self.srv.HASH_PASSWORD_DEFAULT)

    @unittest.skipUnless(shutil.which('git'), 'git non disponibile')
    def test_file_runtime_ignorati_da_git(self):
        for nome in ('config.yaml', 'kiosk.log', 'stato_impegni.json', 'ultimo_reset.txt', 'locandine/ordine.json'):
            percorso = os.path.join(DIR_APP, nome)
            esito = subprocess.run(['git', '-C', RADICE_REPO, 'check-ignore', '-q', percorso])
            self.assertEqual(esito.returncode, 0, f'{nome} non è ignorato')
        tracciati = subprocess.run(['git', '-C', RADICE_REPO, 'ls-files', DIR_APP],
                                   capture_output=True, text=True).stdout
        self.assertNotRegex(tracciati, r'dashboard_aule/config\.yaml')
        self.assertIn('config.example.yaml', tracciati)


class TestHttp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def test_password_default_ammessa_per_configurazione(self):
        self.srv.CONFIG['sicurezza'].update({'admin_ip_autorizzati': [], 'password_admin_hash': HASH_ADMIN})
        status, _, _ = richiesta(self.base + '/api/admin/login', 'POST', json.dumps({'password': 'admin'}).encode(),
                                 {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)

    def test_avviso_sicurezza_su_config_full(self):
        token = login_admin(self.srv, self.base)
        header = {'Content-Type': 'application/json', 'X-Admin-Token': token}
        self.srv.CONFIG['sicurezza']['password_admin_hash'] = HASH_ADMIN
        status, _, corpo = richiesta(self.base + '/api/admin/config_full', 'GET', header=header)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(corpo)['avviso_sicurezza'])

        self.srv.CONFIG['sicurezza']['password_admin_hash'] = 'f' * 64
        status, _, corpo = richiesta(self.base + '/api/admin/config_full', 'GET', header=header)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(corpo)['avviso_sicurezza'])

    def test_url_base_richiede_password_cineca(self):
        token = login_admin(self.srv, self.base)
        originale = self.srv.CONFIG['api_cineca']['url_base']
        header = {'Content-Type': 'application/json', 'X-Admin-Token': token}

        def salva(password):
            corpo = json.dumps({'api_cineca': {'url_base': 'https://altro.example/api', 'password': password}}).encode()
            return richiesta(self.base + '/api/admin/save', 'POST', corpo, header)[0]

        self.assertEqual(salva('********'), 400)
        self.assertEqual(self.srv.CONFIG['api_cineca']['url_base'], originale)
        self.assertEqual(salva('nuova-password'), 200)
        self.assertEqual(self.srv.CONFIG['api_cineca']['url_base'], 'https://altro.example/api')


if __name__ == '__main__':
    unittest.main()
