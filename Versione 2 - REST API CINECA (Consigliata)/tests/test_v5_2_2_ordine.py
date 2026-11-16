"""v5.2.2: ordine logico via ordine.json, cancellazione singola, riconciliazione automatica."""
import json
import os
import unittest

from tests._harness import (JPEG_MINIMO, avvia_http, carica_server, chiudi_server, ferma_http,
                            login_admin, richiesta)

A, B, LEGACY = 'p1000000000001_aaaa.jpg', 'p1000000000002_bbbb.png', '1.jpg'


class TestOrdineLocandine(unittest.TestCase):

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
        for nome in (A, B, LEGACY):
            self.crea(nome)

    def crea(self, nome):
        with open(os.path.join(self.cartella, nome), 'wb') as f:
            f.write(JPEG_MINIMO)

    def lista(self):
        status, _, corpo = richiesta(self.base + '/lista_locandine.json')
        self.assertEqual(status, 200)
        return json.loads(corpo)

    def post(self, percorso, oggetto, autenticato=True):
        header = {'Content-Type': 'application/json'}
        if autenticato:
            header['X-Admin-Token'] = self.token
        return richiesta(self.base + percorso, 'POST', json.dumps(oggetto).encode(), header)

    def test_ordine_naturale_iniziale(self):
        self.assertEqual(self.lista(), [LEGACY, A, B])

    def test_riordino_applicato_e_persistito(self):
        status, _, _ = self.post('/api/admin/locandine/ordine', {'ordine': [B, LEGACY, A]})
        self.assertEqual(status, 200)
        self.assertEqual(self.lista(), [B, LEGACY, A])
        with open(os.path.join(self.cartella, 'ordine.json'), encoding='utf-8') as f:
            self.assertEqual(json.load(f), [B, LEGACY, A])

    def test_riordino_parziale_e_nomi_sconosciuti(self):
        self.post('/api/admin/locandine/ordine', {'ordine': [B, 'inesistente.jpg', B]})
        self.assertEqual(self.lista(), [B, LEGACY, A])

    def test_riordino_payload_non_valido_400(self):
        self.assertEqual(self.post('/api/admin/locandine/ordine', {'ordine': 'x'})[0], 400)

    def test_elimina_senza_rinominare(self):
        self.post('/api/admin/locandine/ordine', {'ordine': [B, A, LEGACY]})
        status, _, _ = self.post('/api/admin/locandine/elimina', {'filename': A})
        self.assertEqual(status, 200)
        self.assertFalse(os.path.exists(os.path.join(self.cartella, A)))
        self.assertEqual(self.lista(), [B, LEGACY])
        self.assertEqual(sorted(os.listdir(self.cartella)), sorted([B, LEGACY, 'ordine.json']))

    def test_elimina_path_traversal_400(self):
        status, _, _ = self.post('/api/admin/locandine/elimina', {'filename': '../server_api.py'})
        self.assertEqual(status, 400)
        self.assertTrue(os.path.exists(os.path.join(self.srv._tmpdir, 'server_api.py')))

    def test_elimina_inesistente_404(self):
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': 'nessuno.jpg'})[0], 404)

    def test_endpoint_admin_richiedono_token(self):
        self.assertEqual(self.post('/api/admin/locandine/ordine', {'ordine': []}, autenticato=False)[0], 401)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': A}, autenticato=False)[0], 401)
        self.assertEqual(richiesta(self.base + '/api/admin/locandine')[0], 401)

    def test_rimozione_manuale_riconciliata(self):
        self.post('/api/admin/locandine/ordine', {'ordine': [B, A, LEGACY]})
        os.remove(os.path.join(self.cartella, A))
        self.assertEqual(self.lista(), [B, LEGACY])

    def test_ordine_corrotto_usa_ordine_naturale(self):
        with open(os.path.join(self.cartella, 'ordine.json'), 'w', encoding='utf-8') as f:
            f.write('{non json')
        self.assertEqual(self.lista(), [LEGACY, A, B])

    def test_file_aggiunto_via_sftp_va_in_coda(self):
        self.post('/api/admin/locandine/ordine', {'ordine': [B, A, LEGACY]})
        nuovo = 'p1000000000009_cccc.jpg'
        self.crea(nuovo)
        self.assertEqual(self.lista(), [B, A, LEGACY, nuovo])

    def test_metadati_admin(self):
        status, _, corpo = richiesta(self.base + '/api/admin/locandine', header={'X-Admin-Token': self.token})
        self.assertEqual(status, 200)
        voci = json.loads(corpo)
        self.assertEqual([v['nome'] for v in voci], [LEGACY, A, B])
        self.assertEqual(set(voci[0]), {'nome', 'kb', 'caricata'})
        self.assertRegex(voci[0]['caricata'], r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$')

    def test_contratto_pubblico_array_di_stringhe(self):
        elenco = self.lista()
        self.assertIsInstance(elenco, list)
        self.assertTrue(all(isinstance(n, str) for n in elenco))

    def test_riordino_edge_cases_validazione(self):
        self.assertEqual(self.post('/api/admin/locandine/ordine', {'ordine': [1, 2, 3]})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/ordine', {'ordine': [A, None]})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/ordine', {})[0], 400)
        # Lista vuota accetta e lascia ordine naturale
        status, _, corpo = self.post('/api/admin/locandine/ordine', {'ordine': []})
        self.assertEqual(status, 200)
        self.assertEqual(self.lista(), [LEGACY, A, B])

    def test_elimina_edge_cases_validazione(self):
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': 123})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': ''})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': 'a/b.jpg'})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': 'a\\b.jpg'})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': '..'})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': '.'})[0], 400)
        self.assertEqual(self.post('/api/admin/locandine/elimina', {'filename': 'a\x00b.jpg'})[0], 400)
        # Supporto campo 'nome' alternativo a 'filename'
        status, _, _ = self.post('/api/admin/locandine/elimina', {'nome': A})
        self.assertEqual(status, 200)
        self.assertFalse(os.path.exists(os.path.join(self.cartella, A)))

    def test_ordine_json_non_lista_usa_ordine_naturale(self):
        with open(os.path.join(self.cartella, 'ordine.json'), 'w', encoding='utf-8') as f:
            json.dump({'errore': 'non e una lista'}, f)
        self.assertEqual(self.lista(), [LEGACY, A, B])

    def test_payload_non_utf8_400(self):
        headers = {'Content-Type': 'application/json', 'X-Admin-Token': self.token}
        status_o, _, corpo_o = richiesta(self.base + '/api/admin/locandine/ordine', 'POST', b'\xff\xff', headers)
        self.assertEqual(status_o, 400)
        self.assertIn('error', json.loads(corpo_o))

        status_e, _, corpo_e = richiesta(self.base + '/api/admin/locandine/elimina', 'POST', b'\xff\xff', headers)
        self.assertEqual(status_e, 400)
        self.assertIn('error', json.loads(corpo_e))

    def test_locandine_file_non_immagine_non_esposto_404(self):
        # ordine.json non deve essere servito come locandina
        with open(os.path.join(self.cartella, 'ordine.json'), 'w', encoding='utf-8') as f:
            json.dump([A], f)
        status_ord, _, _ = richiesta(self.base + '/locandine/ordine.json')
        self.assertEqual(status_ord, 404)

        # File di testo o tmp non devono essere serviti
        with open(os.path.join(self.cartella, 'segreto.txt'), 'w', encoding='utf-8') as f:
            f.write('segreto')
        status_txt, _, _ = richiesta(self.base + '/locandine/segreto.txt')
        self.assertEqual(status_txt, 404)

        # Le immagini invece vengono servite correttamente
        status_img, hdr, _ = richiesta(self.base + f'/locandine/{A}')
        self.assertEqual(status_img, 200)
        content_type = hdr.get('Content-type') or hdr.get('Content-Type')
        self.assertEqual(content_type, 'image/jpeg')


if __name__ == '__main__':
    unittest.main()
