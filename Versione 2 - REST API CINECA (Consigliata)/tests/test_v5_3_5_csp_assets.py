"""v5.3.5: Disaccoppiamento JS/CSS in static/, rimozione handler/style inline, percorsi relativi ./, UI Polish admin e CSP (SEC-06)."""
import os
import re
import subprocess
import unittest

from tests._harness import DIR_APP, avvia_http, carica_server, chiudi_server, ferma_http, richiesta
from tests._harness_js import NODE, esegui_js

CSP_ATTESA = (
    "default-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "style-src 'self'; frame-ancestors 'self'"
)


def leggi_file_grezzo(nome_file):
    with open(os.path.join(DIR_APP, nome_file), encoding='utf-8') as f:
        return f.read()


class TestAuditStaticoFrontend(unittest.TestCase):

    def test_remoto_html_senza_script_style_handler_inline(self):
        html = leggi_file_grezzo('remoto.html')
        script_inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        self.assertEqual([s.strip() for s in script_inline if s.strip()], [])

        style_inline = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
        self.assertEqual([s.strip() for s in style_inline if s.strip()], [])

        handler = re.findall(r'\b(on[a-z]+)\s*=\s*["\'][^"\']*["\']', html, re.IGNORECASE)
        self.assertEqual(handler, [], f'Handler inline residui in remoto.html: {handler}')

        attributi_style = re.findall(r'\bstyle\s*=\s*["\'][^"\']*["\']', html, re.IGNORECASE)
        self.assertEqual(attributi_style, [], f'Attributi style= residui in remoto.html: {attributi_style}')

        self.assertRegex(html, r'<link\s+[^>]*rel=["\']stylesheet["\'][^>]*href=["\']\./static/remoto\.css["\']')
        self.assertRegex(html, r'<script\s+[^>]*src=["\']\./static/remoto\.js["\']')

    def test_admin_html_senza_script_style_handler_inline_e_ui_polish(self):
        html = leggi_file_grezzo('admin.html')
        script_inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        self.assertEqual([s.strip() for s in script_inline if s.strip()], [])

        style_inline = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
        self.assertEqual([s.strip() for s in style_inline if s.strip()], [])

        handler = re.findall(r'\b(on[a-z]+)\s*=\s*["\'][^"\']*["\']', html, re.IGNORECASE)
        self.assertEqual(handler, [], f'Handler inline residui in admin.html: {handler}')

        attributi_style = re.findall(r'\bstyle\s*=\s*["\'][^"\']*["\']', html, re.IGNORECASE)
        self.assertEqual(attributi_style, [], f'Attributi style= residui in admin.html: {attributi_style}')

        self.assertRegex(html, r'<link\s+[^>]*rel=["\']stylesheet["\'][^>]*href=["\']\./static/admin\.css["\']')
        self.assertRegex(html, r'<script\s+[^>]*src=["\']\./static/admin\.js["\']')
        self.assertIn('placeholder="./logo.png"', html)
        self.assertIn('diagnostica_news', html, 'Ancora CSP-safe id="diagnostica_news" mancante in admin.html')

        # Verifica UI Polish: "Interfaccia Dashboard & Digital Signage" (#panel-frontend) prima di #panel-alert e dicitura "(ad esempio):"
        idx_tab_pers = html.index('id="tab-content-personalizzazione"')
        idx_frontend = html.index('id="panel-frontend"')
        idx_alert = html.index('id="panel-alert"')
        idx_locandine = html.index('id="panel-locandine"')
        self.assertGreater(idx_frontend, idx_tab_pers)
        self.assertLess(idx_frontend, idx_alert, '#panel-frontend deve precedere #panel-alert in Personalizzazione')
        self.assertLess(idx_alert, idx_locandine)
        self.assertIn('Interfaccia Dashboard & Digital Signage', html)
        self.assertIn('<code>?kiosk=1</code> (ad esempio):', html)

    def test_asset_esterni_presenti_e_non_vuoti_in_static(self):
        for nome in ('remoto.js', 'remoto.css', 'admin.js', 'admin.css'):
            percorso = os.path.join(DIR_APP, 'static', nome)
            self.assertTrue(os.path.isfile(percorso), f'Asset mancante: static/{nome}')
            self.assertGreater(os.path.getsize(percorso), 0, f'Asset vuoto: static/{nome}')

    def test_js_senza_style_o_handler_inline_nei_template(self):
        for nome in ('remoto.js', 'admin.js'):
            js_src = leggi_file_grezzo(os.path.join('static', nome))
            residui_style = re.findall(r'<[^>]*\bstyle\s*=\s*["\']', js_src, re.IGNORECASE)
            self.assertEqual(residui_style, [], f'Attributi style= in template HTML dentro static/{nome}: {residui_style}')
            residui_on = re.findall(r'<[^>]*\bon[a-z]+\s*=\s*["\']', js_src, re.IGNORECASE)
            self.assertEqual(residui_on, [], f'Handler on*= in template HTML dentro static/{nome}: {residui_on}')
            self.assertNotIn('.style.cssText', js_src, f'Uso vietato di style.cssText in static/{nome}')
            self.assertNotRegex(js_src, r'setAttribute\(\s*["\']style["\']', f'Uso vietato di setAttribute("style") in static/{nome}')

    def test_percorsi_relativi_in_remoto_js_e_admin_js(self):
        remoto_js = leggi_file_grezzo(os.path.join('static', 'remoto.js'))
        self.assertEqual(re.findall(r"fetch\(\s*['\"`]/", remoto_js), [], 'fetch assoluta in static/remoto.js')
        for ep in ('config_pubblica', 'dati.json', 'api/news', 'lista_locandine.json', 'stato'):
            self.assertRegex(remoto_js, r"fetch\(\s*['\"`]\./" + re.escape(ep))

        admin_js = leggi_file_grezzo(os.path.join('static', 'admin.js'))
        self.assertEqual(re.findall(r"fetch\(\s*['\"`]/", admin_js), [], 'fetch assoluta in static/admin.js')
        for ep in (
            'api/admin/login',
            'api/admin/config_full',
            'api/admin/save',
            'api/admin/restart',
            'api/admin/locandine',
            'api/admin/locandine/upload',
            'api/admin/locandine/ordine',
            'api/admin/locandine/elimina',
        ):
            self.assertRegex(admin_js, r"fetch\(\s*['\"`]\./" + re.escape(ep), f'Manca ./ su {ep} in static/admin.js')
        self.assertNotRegex(admin_js, r"['\"`]/locandine/", 'Percorso assoluto /locandine/ in static/admin.js')
        self.assertRegex(admin_js, r"['\"`]\./locandine/")


@unittest.skipUnless(NODE, 'Node.js >= 18 richiesto per i test JS')
class TestSintassiERetrocompatibilitaJS(unittest.TestCase):

    def test_sintassi_node_remoto_e_admin(self):
        for nome in ('remoto.js', 'admin.js'):
            percorso = os.path.join(DIR_APP, 'static', nome)
            esito = subprocess.run([NODE, '--check', percorso], capture_output=True, text=True)
            self.assertEqual(esito.returncode, 0, f'Errore sintassi in static/{nome}: {esito.stderr}')

    def test_harness_js_retrocompatibile_dopo_estrazione(self):
        for target in ('remoto.html', 'static/remoto.js', 'remoto.js'):
            risultato = esegui_js(target, ['escapeHTML'], "escapeHTML('<img src=x>')")
            self.assertEqual(risultato, '&lt;img src=x&gt;', target)


class TestServerCspEAssetStatici(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def setUp(self):
        self.srv.CONFIG['sicurezza'].update({'admin_attivo': True, 'admin_ip_autorizzati': []})

    def test_header_csp_esatto_su_tutti_gli_endpoint(self):
        for percorso in ('/', '/admin', '/dati.json', '/static/remoto.js'):
            status, headers, _ = richiesta(self.base + percorso)
            self.assertEqual(status, 200, percorso)
            headers_lower = {k.lower(): v for k, v in headers.items()}
            self.assertEqual(headers_lower.get('content-security-policy'), CSP_ATTESA, percorso)
            self.assertEqual(headers_lower.get('x-content-type-options'), 'nosniff')
            self.assertEqual(headers_lower.get('x-frame-options'), 'SAMEORIGIN')
            self.assertEqual(headers_lower.get('referrer-policy'), 'no-referrer')

    def test_serving_asset_js_e_css_con_mime_corretto(self):
        attesi = [
            ('/static/remoto.js', 'javascript'),
            ('/static/remoto.css', 'text/css'),
            ('/static/admin.js', 'javascript'),
            ('/static/admin.css', 'text/css'),
        ]
        for path, mime_sub in attesi:
            status, headers, corpo = richiesta(self.base + path)
            self.assertEqual(status, 200, path)
            ct = {k.lower(): v for k, v in headers.items()}.get('content-type', '')
            self.assertIn(mime_sub, ct.lower(), path)
            self.assertGreater(len(corpo), 0, path)

    def test_admin_asset_protetti_da_sicurezza_e_no_traversal(self):
        self.srv.CONFIG['sicurezza']['admin_attivo'] = False
        status_js, _, _ = richiesta(self.base + '/static/admin.js')
        status_css, _, _ = richiesta(self.base + '/static/admin.css')
        self.assertEqual(status_js, 404)
        self.assertEqual(status_css, 404)

        # Gli asset pubblici del totem devono restare accessibili anche con admin_attivo=False
        status_rem_js, _, _ = richiesta(self.base + '/static/remoto.js')
        status_rem_css, _, _ = richiesta(self.base + '/static/remoto.css')
        self.assertEqual(status_rem_js, 200)
        self.assertEqual(status_rem_css, 200)

        for tentativo in (
            '/static/remoto.js/../../../etc/passwd',
            '/static/../config.yaml',
            '/static/%2e%2e/config.yaml',
            '/static/..%2fserver_api.py',
            '/static/inesistente.js',
        ):
            status_trav, _, _ = richiesta(self.base + tentativo)
            self.assertEqual(status_trav, 404, tentativo)


if __name__ == '__main__':
    unittest.main()
