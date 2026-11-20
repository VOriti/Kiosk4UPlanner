"""v5.2.8: escape all'uscita su tutte le interpolazioni HTML, ricerca News Hub, Referrer-Policy."""
import re
import unittest

from tests._harness import avvia_http, carica_server, chiudi_server, ferma_http, richiesta
from tests._harness_js import NODE, esegui_js, estrai_funzione_js, leggi_pagina

# Variabili interne composte solo da frammenti già sottoposti a escape, da classi CSS fisse o da numeri.
CONSENTITE = {
    'stileTesto', 'classeStato', 'classeBadge', 'iconaStato', 'htmlAvviso', 'htmlInCorso', 'htmlFuturi',
    'htmlContenuto', 'testoInterno', 'stringaUnica', 'link', 'durata', 'conteggio',
    'k',   # id DOM in getElementById(`th-sort-${k}`), non HTML
    'ora', # testo del badge di freschezza (v5.2.5), assegnato con textContent, non HTML
}
PAYLOAD = '<img src=x onerror=alert(1)>'


class TestAuditStatico(unittest.TestCase):

    def test_ogni_interpolazione_e_sottoposta_a_escape(self):
        html = leggi_pagina('remoto.html')
        violazioni = [e for e in (m.strip() for m in re.findall(r'\$\{([^}]*)\}', html))
                      if e not in CONSENTITE and not e.startswith('escapeHTML(')]
        self.assertEqual(violazioni, [], f'Interpolazioni senza escapeHTML: {violazioni}')

    def test_nessun_handler_inline_con_dati(self):
        self.assertNotIn("toggleNewsSource('${", leggi_pagina('remoto.html'))

    def test_formatta_titolo_usa_domparser(self):
        sorgente = estrai_funzione_js('remoto.html', 'formattaTitoloNews')
        self.assertIn('DOMParser', sorgente)
        self.assertNotIn('innerHTML', sorgente)

    def test_campo_ricerca(self):
        self.assertIn('id="news-search"', leggi_pagina('remoto.html'))


@unittest.skipUnless(NODE, 'Node.js non disponibile')
class TestComportamento(unittest.TestCase):

    def test_escape_html(self):
        r = esegui_js('remoto.html', ['escapeHTML'], '[escapeHTML(`<a href="x">&\'`), escapeHTML(null), escapeHTML(0)]')
        self.assertEqual(r, ['&lt;a href=&quot;x&quot;&gt;&amp;&#39;', '', '0'])

    def test_card_con_dati_ostili(self):
        imp = ('{titolo:%r, aula:%r, docente:%r, orario:"9", avviso:%r, inCorso:true, cancellato:false}'
               % (PAYLOAD, PAYLOAD, PAYLOAD, PAYLOAD))
        card = esegui_js('remoto.html', ['escapeHTML', 'generaCardHTML'], f'generaCardHTML({imp})',
                         prologo='const CONFIG_APP = {mostraStatoPC: true};')
        self.assertNotIn('<img', card)
        self.assertIn('&lt;img', card)

    def test_ricerca(self):
        r = esegui_js('remoto.html', ['notiziaCorrisponde'],
                      '[notiziaCorrisponde({titolo:"Bando Erasmus",fonte:"Ateneo"},"erasmus"),'
                      ' notiziaCorrisponde({titolo:"Bando",fonte:"Ateneo"},"ATEN"),'
                      ' notiziaCorrisponde({titolo:"Bando",fonte:"Ateneo"},"mensa"),'
                      ' notiziaCorrisponde({titolo:"Bando",fonte:"Ateneo"},"")]')
        self.assertEqual(r, [True, True, False, True])


class TestHeader(unittest.TestCase):

    def test_referrer_policy(self):
        srv = carica_server()
        base, httpd = avvia_http(srv)
        try:
            for percorso in ('/', '/dati.json'):
                self.assertEqual(richiesta(base + percorso)[1].get('Referrer-Policy'), 'no-referrer')
        finally:
            ferma_http(httpd)
            chiudi_server(srv)


if __name__ == '__main__':
    unittest.main()
