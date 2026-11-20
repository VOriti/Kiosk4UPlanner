"""v5.2.3: niente Date.now() sulle locandine, ridimensionamento lato client a 2160 px."""
import unittest

from tests._harness_js import NODE, esegui_js, estrai_funzione_js, leggi_pagina


class TestCacheLocandine(unittest.TestCase):

    def test_nessun_cache_busting_temporale(self):
        sorgente = estrai_funzione_js('remoto.html', 'riproduciLocandine')
        self.assertNotIn('Date.now', sorgente)
        self.assertIn('urlLocandina(', sorgente)

    def test_admin_ridimensiona_prima_dell_upload(self):
        admin = leggi_pagina('admin.html')
        self.assertRegex(admin, r'LATO_MAX_LOCANDINA\s*=\s*2160')
        self.assertIn('createImageBitmap', admin)
        sorgente_carica = estrai_funzione_js('admin.html', 'caricaLocandine')
        self.assertIn('preparaLocandina(', sorgente_carica)
        self.assertIn('blob.type', sorgente_carica)
        self.assertIn('Locandina ridimensionata e caricata con successo!', sorgente_carica)
        self.assertIn('Locandina caricata con successo!', sorgente_carica)
        sorgente_toast = estrai_funzione_js('admin.html', 'showToast')
        self.assertIn('messaggio', sorgente_toast)

        if NODE:
            prologo = """
            let currentText = 'Salvato con successo!';
            let classes = [];
            let toastTimeout = null;
            let queuedTimer = null;
            const mockToast = {
                get textContent() { return currentText; },
                set textContent(v) { currentText = v; },
                classList: {
                    add: (c) => { if (!classes.includes(c)) classes.push(c); },
                    remove: (c) => { classes = classes.filter(x => x !== c); },
                    contains: (c) => classes.includes(c)
                },
                get offsetWidth() { return 100; }
            };
            global.document = { getElementById: (id) => id === 'toast' ? mockToast : null };
            const setTimeout = (cb, ms) => { queuedTimer = cb; return 42; };
            const clearTimeout = (id) => { queuedTimer = null; };
            """
            expr = (
                '(() => {'
                '  showToast("Locandina ridimensionata e caricata con successo!");'
                '  const prima = { text: currentText, show: classes.includes("show") };'
                '  if (queuedTimer) queuedTimer();'
                '  const dopo = { text: currentText, show: classes.includes("show") };'
                '  showToast();'
                '  const fallback = { text: currentText, show: classes.includes("show") };'
                '  return { prima, dopo, fallback };'
                '})()'
            )
            res = esegui_js('admin.html', ['showToast'], expr, prologo=prologo)
            self.assertEqual(res['prima'], {'text': 'Locandina ridimensionata e caricata con successo!', 'show': True})
            self.assertEqual(res['dopo'], {'text': 'Salvato con successo!', 'show': False})
            self.assertEqual(res['fallback'], {'text': 'Salvato con successo!', 'show': True})

    def test_prepara_locandina_struttura_e_fallback(self):
        sorgente = estrai_funzione_js('admin.html', 'preparaLocandina')
        self.assertIn('image/webp', sorgente)
        self.assertIn('image/jpeg', sorgente)
        self.assertIn('#ffffff', sorgente)
        self.assertIn('destination-over', sorgente)
        self.assertIn('bitmap.close()', sorgente)


@unittest.skipUnless(NODE, 'Node.js non disponibile')
class TestFunzioniPure(unittest.TestCase):

    def dim(self, w, h):
        return esegui_js('admin.html', ['calcolaDimensioniLocandina'], f'calcolaDimensioniLocandina({w}, {h}, 2160)')

    def test_verticale_grande(self):
        self.assertEqual(self.dim(6000, 8000), {'larghezza': 1620, 'altezza': 2160, 'ridimensiona': True})

    def test_orizzontale_grande(self):
        self.assertEqual(self.dim(3000, 1000), {'larghezza': 2160, 'altezza': 720, 'ridimensiona': True})

    def test_gia_entro_limite(self):
        self.assertEqual(self.dim(1080, 1920), {'larghezza': 1080, 'altezza': 1920, 'ridimensiona': False})

    def test_esatto_limite(self):
        self.assertEqual(self.dim(2160, 2160), {'larghezza': 2160, 'altezza': 2160, 'ridimensiona': False})

    def test_quadrata_grande(self):
        self.assertEqual(self.dim(3000, 3000), {'larghezza': 2160, 'altezza': 2160, 'ridimensiona': True})

    def test_url_locandina_codificato(self):
        url = esegui_js('remoto.html', ['urlLocandina'], 'urlLocandina("l\'evento 1.jpg")')
        self.assertTrue(url.endswith("locandine/l%27evento%201.jpg"), url)

    def test_url_locandina_standard(self):
        url = esegui_js('remoto.html', ['urlLocandina'], 'urlLocandina("p1700000000000_abcd.webp")')
        self.assertEqual(url, "./locandine/p1700000000000_abcd.webp")

    def test_url_locandina_caratteri_speciali(self):
        url = esegui_js('remoto.html', ['urlLocandina'], 'urlLocandina("locandina & evento \'speciale\' (2026).png")')
        self.assertEqual(url, "./locandine/locandina%20%26%20evento%20%27speciale%27%20(2026).png")


if __name__ == '__main__':
    unittest.main()
