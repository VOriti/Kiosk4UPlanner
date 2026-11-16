"""v5.2.1: upload binario grezzo, nomi immutabili, Content-Length robusto, rotazione log di sistema."""
import json
import os
import re
import unittest

from tests._harness import (DIR_APP, JPEG_MINIMO, PNG_MINIMO, WEBP_MINIMO, avvia_http, carica_server,
                            chiudi_server, ferma_http, login_admin, post_grezzo, richiesta)

RE_NOME = re.compile(r'^p\d{13}_[0-9a-f]{4}\.(jpg|png|webp)$')
PERCORSO_UPLOAD = '/api/admin/locandine/upload'


class TestUploadLocandine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)
        cls.token = login_admin(cls.srv, cls.base)
        cls.cartella = os.path.join(cls.srv._tmpdir, 'locandine')

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def setUp(self):
        for nome in os.listdir(self.cartella):
            os.remove(os.path.join(self.cartella, nome))

    def upload(self, corpo, autenticato=True, header_extra=None):
        header = {'Content-Type': 'application/octet-stream'}
        if autenticato:
            header['X-Admin-Token'] = self.token
        header.update(header_extra or {})
        return richiesta(self.base + PERCORSO_UPLOAD, 'POST', corpo, header)

    def test_formati_ammessi_con_nome_immutabile(self):
        for corpo, ext in ((JPEG_MINIMO, '.jpg'), (PNG_MINIMO, '.png'), (WEBP_MINIMO, '.webp')):
            status, _, risposta = self.upload(corpo)
            self.assertEqual(status, 200, risposta)
            nome = json.loads(risposta)['filename']
            self.assertRegex(nome, RE_NOME)
            self.assertTrue(nome.endswith(ext))
            with open(os.path.join(self.cartella, nome), 'rb') as f:
                self.assertEqual(f.read(), corpo)

    def test_nome_del_client_ignorato(self):
        status, _, risposta = self.upload(JPEG_MINIMO, header_extra={'X-Filename': '../../evil.jpg'})
        self.assertEqual(status, 200)
        self.assertRegex(json.loads(risposta)['filename'], RE_NOME)
        self.assertFalse(os.path.exists(os.path.join(self.srv._tmpdir, 'evil.jpg')))

    def test_formato_non_ammesso_400_senza_residui(self):
        status, _, _ = self.upload(b'<?php echo 1; ?>' + b' ' * 64)
        self.assertEqual(status, 400)
        self.assertEqual(os.listdir(self.cartella), [])

    def test_upload_body_vuoto_400(self):
        status, _, corpo = self.upload(b'')
        self.assertEqual(status, 400)
        self.assertIn('Body vuoto', json.loads(corpo).get('error', ''))
        self.assertEqual(os.listdir(self.cartella), [])

    def test_upload_interrotto_solleva_valueerror_e_pulisce(self):
        import io
        stream_rotto = io.BytesIO(b'12345')
        with self.assertRaises(ValueError) as ctx:
            self.srv.salva_locandina_da_stream(stream_rotto, 100)
        self.assertIn('Upload interrotto', str(ctx.exception))
        self.assertEqual(os.listdir(self.cartella), [])

    def test_senza_token_401(self):
        status, _, _ = self.upload(JPEG_MINIMO, autenticato=False)
        self.assertEqual(status, 401)
        self.assertEqual(os.listdir(self.cartella), [])

    def test_content_length_negativo_400(self):
        status, _ = post_grezzo(self.base, PERCORSO_UPLOAD,
                                [('X-Admin-Token', self.token), ('Content-Length', '-1')])
        self.assertEqual(status, 400)

    def test_content_length_non_numerico_400_e_server_vivo(self):
        status, _ = post_grezzo(self.base, PERCORSO_UPLOAD,
                                [('X-Admin-Token', self.token), ('Content-Length', 'abc')])
        self.assertEqual(status, 400)
        self.assertEqual(richiesta(self.base + '/dati.json')[0], 200)

    def test_oltre_limite_413(self):
        status, _ = post_grezzo(self.base, PERCORSO_UPLOAD,
                                [('X-Admin-Token', self.token),
                                 ('Content-Length', str(10 * 1024 * 1024 + 1))])
        self.assertEqual(status, 413)

    def test_login_content_length_negativo_400(self):
        status, _ = post_grezzo(self.base, '/api/admin/login', [('Content-Length', '-1')])
        self.assertEqual(status, 400)

    def test_elenco_misto_legacy_e_nuovi(self):
        for nome in ('10.png', '2.jpg', '1.jpg'):
            with open(os.path.join(self.cartella, nome), 'wb') as f:
                f.write(JPEG_MINIMO)
        self.upload(JPEG_MINIMO)
        status, _, corpo = richiesta(self.base + '/lista_locandine.json')
        elenco = json.loads(corpo)
        self.assertEqual(status, 200)
        self.assertEqual(elenco[:3], ['1.jpg', '2.jpg', '10.png'])
        self.assertRegex(elenco[3], RE_NOME)

    def test_orfani_di_upload_rimossi(self):
        orfano = os.path.join(self.cartella, '.upload_abc.tmp')
        open(orfano, 'wb').close()
        self.assertNotIn('.upload_abc.tmp', json.loads(richiesta(self.base + '/lista_locandine.json')[2]))
        self.srv.pulisci_upload_orfani()
        self.assertFalse(os.path.exists(orfano))

    def test_xinitrc_ruota_il_log_di_sistema(self):
        with open(os.path.join(DIR_APP, '..', '.xinitrc'), encoding='utf-8') as f:
            xinitrc = f.read()
        self.assertIn('5242880', xinitrc)
        self.assertIn('.1"', xinitrc)


if __name__ == '__main__':
    unittest.main()
