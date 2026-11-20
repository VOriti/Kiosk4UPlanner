"""v5.2.9: miniature lazy proporzionate, lightbox con metadati, escape in admin.html."""
import re
import unittest

from tests._harness_js import NODE, esegui_js, leggi_pagina


class TestMiniature(unittest.TestCase):

    def setUp(self):
        self.admin = leggi_pagina('admin.html')

    def test_miniature(self):
        self.assertIn('loading="lazy"', self.admin)
        self.assertRegex(self.admin, r'max-height:\s*70px')
        self.assertRegex(self.admin, r'object-fit:\s*contain')

    def test_lightbox_con_metadati(self):
        self.assertIn('function apriLightbox', self.admin)
        for campo in ('kb', 'caricata'):
            self.assertIn(campo, self.admin)

    def test_campi_fonti_sottoposti_a_escape(self):
        self.assertNotRegex(self.admin, r'\$\{f\.(nome|url)\b')


@unittest.skipUnless(NODE, 'Node.js non disponibile')
class TestEscapeAdmin(unittest.TestCase):

    def test_stessa_semantica_di_remoto(self):
        espressione = 'escapeHTML(`<x y="1">&\'`)'
        self.assertEqual(esegui_js('admin.html', ['escapeHTML'], espressione),
                         esegui_js('remoto.html', ['escapeHTML'], espressione))


if __name__ == '__main__':
    unittest.main()
