"""v5.2.6: scarica_fonte con timeout 5 s, decodifica da byte, clean_html multilinea, pesi 1-5."""
import unittest
from unittest import mock

from tests._harness import carica_server, chiudi_server

RSS_UTF8 = ('<?xml version="1.0" encoding="UTF-8"?><rss><channel>'
            '<item><title>Università e caffè</title><link>https://a.it/1</link>'
            '<pubDate>Mon, 09 Nov 2026 10:00:00 +0100</pubDate></item></channel></rss>').encode('utf-8')
ATOM = (b'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
        b'<entry><title>Bando</title><link href="https://a.it/b"/><updated>2026-11-09T10:00:00Z</updated></entry></feed>')


class RispostaFinta:
    def __init__(self, content=b'', dati_json=None, status=200):
        self.content, self._json, self.status_code = content, dati_json, status

    @property
    def text(self):
        return self.content.decode('iso-8859-1')   # come requests con text/xml senza charset

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class TestNews(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()

    @classmethod
    def tearDownClass(cls):
        chiudi_server(cls.srv)

    def fonte(self, tipo='rss', url='https://feed.test/rss', **extra):
        f = {'nome': 'Test', 'url': url, 'tipo': tipo, 'abilitata': True, 'visibile_di_default': True, 'peso': 1}
        f.update(extra)
        return f

    def test_rss_utf8_senza_charset(self):
        with mock.patch.object(self.srv.requests, 'get', return_value=RispostaFinta(RSS_UTF8)):
            notizie = self.srv.scarica_fonte(self.fonte())
        self.assertEqual(notizie[0]['titolo'], 'Università e caffè')
        self.assertEqual(notizie[0]['data'], '09/11/2026')

    def test_timeout_di_5_secondi(self):
        with mock.patch.object(self.srv.requests, 'get', return_value=RispostaFinta(RSS_UTF8)) as get:
            self.srv.scarica_fonte(self.fonte())
        self.assertEqual(get.call_args.kwargs['timeout'], 5)

    def test_atom(self):
        with mock.patch.object(self.srv.requests, 'get', return_value=RispostaFinta(ATOM)):
            notizie = self.srv.scarica_fonte(self.fonte())
        self.assertEqual((notizie[0]['titolo'], notizie[0]['link']), ('Bando', 'https://a.it/b'))

    def test_rest_wordpress(self):
        dati = [{'title': {'rendered': 'Ciao <b>mondo</b>'}, 'link': 'https://a.it/w', 'date': '2026-11-09T10:00:00'}]
        with mock.patch.object(self.srv.requests, 'get', return_value=RispostaFinta(dati_json=dati)):
            notizie = self.srv.scarica_fonte(self.fonte(tipo='rest'))
        self.assertEqual(notizie[0]['titolo'], 'Ciao mondo')

    def test_clean_html_multilinea(self):
        self.assertEqual(self.srv.clean_html('<img\nsrc=x onerror=alert(1)>Titolo'), 'Titolo')

    def test_normalizza_peso(self):
        casi = {'3': 3, 0: 1, 9: 5, 'abc': 1, None: 1, 2.7: 2}
        for valore, atteso in casi.items():
            self.assertEqual(self.srv.normalizza_peso(valore), atteso, valore)

    def test_interleaving_pesato_e_fonte_in_errore(self):
        def get_finto(url, timeout):
            if 'rotta' in url:
                raise ConnectionError('irraggiungibile')
            n = 3 if 'a.test' in url else 1
            voci = ''.join(f'<item><title>{url[8]}{i}</title></item>' for i in range(n))
            return RispostaFinta(f'<rss><channel>{voci}</channel></rss>'.encode())
        self.srv.CONFIG['footer_news'] = {'abilitato': True, 'fonti': [
            self.fonte(url='https://a.test/rss', nome='A', peso=2),
            self.fonte(url='https://b.test/rss', nome='B', peso='9'),
            self.fonte(url='https://rotta.test/rss', nome='R')]}
        with mock.patch.object(self.srv.requests, 'get', side_effect=get_finto):
            self.srv.aggiorna_news_una_volta()
        self.assertEqual([n['titolo'] for n in self.srv.memoria_news], ['a0', 'a1', 'b0', 'a2'])


if __name__ == '__main__':
    unittest.main()
