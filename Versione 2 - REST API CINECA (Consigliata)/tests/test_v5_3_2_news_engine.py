"""v5.3.2: NewsEngine autonomo, confinamento totale in RAM, timeout 5s, binary XML e semaforo."""
import builtins
import datetime
import sys
import unittest
from unittest import mock

import requests

from tests._harness import DIR_APP, carica_server, chiudi_server

if DIR_APP not in sys.path:
    sys.path.insert(0, DIR_APP)

from core.news_engine import TIMEOUT_FONTE_SEC, NewsEngine

RSS_UTF8_SENZA_CHARSET = (
    '<?xml version="1.0" encoding="UTF-8"?><rss><channel>'
    '<item><title>Università e novità — caffè</title><link>https://unipv.it/n1</link>'
    '<pubDate>Mon, 23 Nov 2026 09:30:00 +0100</pubDate></item>'
    '</channel></rss>'
).encode('utf-8')

ATOM_VALIDO = (
    b'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
    b'<entry><title>Bando ricerca</title><link href="https://unipv.it/atom1"/>'
    b'<updated>2026-11-23T08:00:00Z</updated></entry></feed>'
)


class RispostaFintaNews:
    def __init__(self, content=b'', json_data=None, status_code=200):
        self.content = content
        self._json = json_data
        self.status_code = status_code

    @property
    def text(self):
        return self.content.decode('iso-8859-1', errors='replace')

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}', response=self)


class TestNewsEngine(unittest.TestCase):

    def setUp(self):
        self.fonti = [
            {
                'nome': 'Ateneo',
                'url': 'https://a.test/rss',
                'tipo': 'rss',
                'abilitata': True,
                'visibile_di_default': True,
                'peso': 2,
            },
            {
                'nome': 'Dipartimento',
                'url': 'https://b.test/wp-json',
                'tipo': 'rest',
                'abilitata': True,
                'visibile_di_default': True,
                'peso': 9,
            },
            {
                'nome': 'Disabilitata',
                'url': 'https://off.test/rss',
                'tipo': 'rss',
                'abilitata': False,
                'visibile_di_default': False,
                'peso': 1,
            },
        ]
        self.engine = NewsEngine(self.fonti, cache_ttl=300)

    def test_normalizza_peso_e_clean_html_dotall(self):
        self.assertEqual(TIMEOUT_FONTE_SEC, 5)
        self.assertEqual(NewsEngine.normalizza_peso(0), 1)
        self.assertEqual(NewsEngine.normalizza_peso(3), 3)
        self.assertEqual(NewsEngine.normalizza_peso(12), 5)
        self.assertEqual(NewsEngine.normalizza_peso('non-valido'), 1)
        self.assertEqual(NewsEngine.normalizza_peso(None), 1)

        grezzo = "<div>Titolo<br>\ncon <img\nsrc=x\nonerror=alert(1)>testo pulito</div>"
        pulito = NewsEngine.clean_html(grezzo)
        self.assertEqual(pulito, 'Titolo\ncon testo pulito')
        self.assertNotIn('<img', pulito)

    def test_parse_data_notizia_formati_omogenei(self):
        self.assertEqual(NewsEngine.parse_data_notizia('Mon, 23 Nov 2026 10:00:00 +0100'), '23/11/2026')
        self.assertEqual(NewsEngine.parse_data_notizia('2026-11-23T14:20:00Z'), '23/11/2026')
        self.assertEqual(NewsEngine.parse_data_notizia('23 novembre 2026'), '23/11/2026')
        self.assertEqual(NewsEngine.parse_data_notizia('5/1/2026'), '05/01/2026')

    @mock.patch('core.news_engine.requests.get')
    def test_parsing_binario_utf8_atom_e_timeout_5s(self, mock_get):
        mock_get.return_value = RispostaFintaNews(content=RSS_UTF8_SENZA_CHARSET)
        notizie_rss = self.engine.scarica_fonte(self.fonti[0])
        self.assertEqual(mock_get.call_args.kwargs['timeout'], 5)
        self.assertEqual(notizie_rss[0]['titolo'], 'Università e novità — caffè')
        self.assertEqual(notizie_rss[0]['data'], '23/11/2026')

        mock_get.return_value = RispostaFintaNews(content=ATOM_VALIDO)
        notizie_atom = self.engine.scarica_fonte(self.fonti[0])
        self.assertEqual(notizie_atom[0]['titolo'], 'Bando ricerca')
        self.assertEqual(notizie_atom[0]['link'], 'https://unipv.it/atom1')

    @mock.patch('core.news_engine.requests.get')
    def test_isolamento_errori_timeout_http_e_xml_malformato(self, mock_get):
        def finto_get(url, timeout):
            self.assertEqual(timeout, 5)
            if 'timeout' in url:
                raise requests.exceptions.Timeout('Timeout 5s scaduto')
            if '404' in url:
                return RispostaFintaNews(status_code=404)
            if 'rotto' in url:
                return RispostaFintaNews(content=b'<rss><channel><item><title>Non chiuso')
            return RispostaFintaNews(content=RSS_UTF8_SENZA_CHARSET)

        mock_get.side_effect = finto_get
        fonti_test = [
            {'nome': 'Timeout', 'url': 'https://timeout.test/rss', 'tipo': 'rss', 'abilitata': True, 'peso': 1},
            {'nome': 'NotFound', 'url': 'https://404.test/rss', 'tipo': 'rss', 'abilitata': True, 'peso': 1},
            {'nome': 'XmlRotto', 'url': 'https://rotto.test/rss', 'tipo': 'rss', 'abilitata': True, 'peso': 1},
            {'nome': 'Disabilitata', 'url': 'https://off.test/rss', 'tipo': 'rss', 'abilitata': False, 'peso': 1},
            {'nome': 'Valida', 'url': 'https://ok.test/rss', 'tipo': 'rss', 'abilitata': True, 'peso': 1},
        ]
        self.engine.set_fonti(fonti_test)
        notizie = self.engine.aggiorna()
        diag = self.engine.get_diagnostica()

        self.assertEqual(len(notizie), 1)
        self.assertEqual(diag['https://timeout.test/rss']['stato'], 'Timeout')
        self.assertEqual(diag['https://timeout.test/rss']['semaforo'], '🔴')
        self.assertEqual(diag['https://404.test/rss']['stato'], 'HTTP 404')
        self.assertEqual(diag['https://rotto.test/rss']['stato'], 'Errore formato XML')
        self.assertEqual(diag['https://off.test/rss']['stato'], 'DISABILITATA')
        self.assertEqual(diag['https://off.test/rss']['semaforo'], '⚪')
        self.assertEqual(diag['https://ok.test/rss']['stato'], 'OK')
        self.assertEqual(diag['https://ok.test/rss']['semaforo'], '🟢')

    @mock.patch('core.news_engine.requests.get')
    def test_interleaving_pesato_e_confinamento_ram_zero_io(self, mock_get):
        def finto_get(url, timeout):
            if 'a.test' in url:
                voci = ''.join(f'<item><title>A{i}</title></item>' for i in range(3))
                return RispostaFintaNews(content=f'<rss><channel>{voci}</channel></rss>'.encode())
            return RispostaFintaNews(
                json_data=[{'title': {'rendered': '<b>B0</b>'}, 'link': 'https://b.test/0', 'date': '2026-11-23T10:00:00'}]
            )

        mock_get.side_effect = finto_get
        tz_preinizializzata = datetime.timezone(datetime.timedelta(hours=1))
        with mock.patch.object(builtins, 'open', side_effect=AssertionError('Scrittura o lettura su disco vietata')) as mock_open:
            risultato = self.engine.aggiorna(tz_roma=tz_preinizializzata)
        mock_open.assert_not_called()
        self.assertEqual([n['titolo'] for n in risultato], ['A0', 'A1', 'B0', 'A2'])
        self.assertEqual([n['titolo'] for n in self.engine.get_news()], ['A0', 'A1', 'B0', 'A2'])

    def test_delega_server_api_retrocompatibile(self):
        srv = carica_server()
        try:
            srv.CONFIG['footer_news'] = {
                'abilitato': True,
                'fonti': [self.fonti[0]],
            }
            with mock.patch.object(srv.requests, 'get', return_value=RispostaFintaNews(content=RSS_UTF8_SENZA_CHARSET)):
                srv.aggiorna_news_una_volta()
            self.assertEqual(len(srv.memoria_news), 1)
            self.assertEqual(srv.DIAGNOSTICA_NEWS['https://a.test/rss']['stato'], 'OK')
        finally:
            chiudi_server(srv)


if __name__ == '__main__':
    unittest.main()
