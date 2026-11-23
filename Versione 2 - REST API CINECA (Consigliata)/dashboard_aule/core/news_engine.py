"""Motore RSS/Atom/REST autonomo confinato integralmente in RAM (zero I/O su MicroSD)."""
import datetime
import email.utils
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET

import requests

from core.cineca_client import get_tz_roma

TIMEOUT_FONTE_SEC = 5
TZ_ROMA = get_tz_roma()

_RE_HTML_TAG = re.compile(r'<.*?>', re.DOTALL)
_MESI_IT = {
    'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
    'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12,
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
    'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
}


class NewsEngine:
    """Motore di aggregazione feed news confinato in RAM con interleaving pesato e semaforo diagnostico."""

    TIMEOUT_FONTE_SEC = TIMEOUT_FONTE_SEC

    def __init__(self, fonti_config=None, cache_ttl=300):
        self.fonti = list(fonti_config or [])
        self.cache_ttl = int(cache_ttl)
        self.memoria_news = []
        self.diagnostica = {}
        self.ultimo_aggiornamento = 0.0
        self._lock = threading.Lock()

    def set_fonti(self, nuove_fonti):
        """Aggiorna la lista di fonti configurate in modo thread-safe."""
        with self._lock:
            self.fonti = list(nuove_fonti or [])

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Rimuove tutti i tag HTML anche multilinea tramite regex con re.DOTALL."""
        if not raw_html:
            return ""
        return _RE_HTML_TAG.sub('', str(raw_html)).strip()

    @staticmethod
    def normalizza_peso(valore) -> int:
        """Forza il peso intero nell'intervallo [1, 5] con fallback a 1."""
        try:
            return min(5, max(1, int(valore)))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def parse_data_notizia(raw: str) -> str:
        """Normalizza date RFC 822, DD/MM/YYYY, testuali italiane e ISO 8601 in DD/MM/YYYY."""
        if not raw:
            return ''
        raw = raw.strip()
        try:
            dt = email.utils.parsedate_to_datetime(raw)
            if dt:
                return dt.strftime('%d/%m/%Y')
        except Exception:
            pass
        m1 = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', raw)
        if m1:
            d, m, y = m1.groups()
            return f"{int(d):02d}/{int(m):02d}/{y}"
        m2 = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})', raw)
        if m2:
            d, mese_str, y = m2.groups()
            mese_num = _MESI_IT.get(mese_str.lower()[:3]) or _MESI_IT.get(mese_str.lower())
            if mese_num:
                return f"{int(d):02d}/{mese_num:02d}/{y}"
        m3 = re.search(r'(\d{4})-(\d{2})-(\d{2})', raw)
        if m3:
            y, m, d = m3.groups()
            return f"{int(d):02d}/{int(m):02d}/{y}"
        return raw

    @staticmethod
    def classifica_errore_fonte(exc: Exception) -> str:
        """Classifica in stringa leggibile l'errore di recupero o parsing di una fonte."""
        risposta = getattr(exc, 'response', None)
        if risposta is not None and getattr(risposta, 'status_code', None):
            return f"HTTP {risposta.status_code}"
        if 'Timeout' in type(exc).__name__:
            return "Timeout"
        if isinstance(exc, ET.ParseError):
            return "Errore formato XML"
        if isinstance(exc, ValueError):
            return "Errore formato JSON"
        return "Errore di rete"

    def scarica_fonte(self, fonte: dict) -> list[dict]:
        """Scarica e normalizza gli articoli di una singola fonte (RSS/Atom binario o WordPress REST)."""
        url = str(fonte.get('url') or '').strip()
        tipo = str(fonte.get('tipo') or '').lower()
        nome = fonte.get('nome', 'Fonte')
        visibile = fonte.get('visibile_di_default', True)

        if not url:
            return []

        notizie_di_questa_fonte = []
        res = requests.get(url, timeout=self.TIMEOUT_FONTE_SEC)
        res.raise_for_status()

        if tipo == 'rest':
            dati = res.json()
            for item in dati:
                title = item.get('title', {}).get('rendered', '')
                link = item.get('link', '')
                data = self.parse_data_notizia(item.get('date', ''))
                titolo_pulito = self.clean_html(title)
                if titolo_pulito:
                    notizie_di_questa_fonte.append({
                        "fonte": nome,
                        "titolo": titolo_pulito,
                        "link": link,
                        "data": data,
                        "visibile": visibile,
                    })
        elif tipo == 'rss':
            root = ET.fromstring(res.content)
            items = root.findall('./channel/item')
            if not items:
                items = (
                    root.findall('.//{http://www.w3.org/2005/Atom}entry')
                    or root.findall('.//entry')
                )

            for item in items:
                atom_title = item.find('{http://www.w3.org/2005/Atom}title')
                title = atom_title if atom_title is not None else item.find('title')
                atom_link = item.find('{http://www.w3.org/2005/Atom}link')
                link_elem = atom_link if atom_link is not None else item.find('link')
                date_elem = None
                for tag_candidate in (
                    '{http://www.w3.org/2005/Atom}updated',
                    '{http://www.w3.org/2005/Atom}published',
                    'pubDate',
                    '{http://purl.org/dc/elements/1.1/}date',
                    'date',
                ):
                    found_el = item.find(tag_candidate)
                    if found_el is not None:
                        date_elem = found_el
                        break

                link = ''
                if link_elem is not None:
                    link = link_elem.get('href', '') or (link_elem.text.strip() if link_elem.text else '')
                raw_data = date_elem.text.strip() if date_elem is not None and date_elem.text else ''
                data = self.parse_data_notizia(raw_data)

                titolo_raw = "".join(title.itertext()).strip() if title is not None else ""
                if not link and title is not None:
                    a_elem = title.find('.//a')
                    if a_elem is not None and a_elem.get('href'):
                        link = a_elem.get('href')
                    elif 'href=' in str(titolo_raw):
                        m_href = re.search(r'href="([^"]+)"', str(titolo_raw)) or re.search(
                            r"href='([^']+)'", str(titolo_raw)
                        )
                        if m_href:
                            link = m_href.group(1).strip()

                titolo_pulito = self.clean_html(titolo_raw)
                if titolo_pulito:
                    notizie_di_questa_fonte.append({
                        "fonte": nome,
                        "titolo": titolo_pulito,
                        "link": link.strip(),
                        "data": data,
                        "visibile": visibile,
                    })
        return notizie_di_questa_fonte

    def _valuta_fonte(self, fonte: dict, tz) -> tuple[str, list[dict], dict]:
        """Valuta una singola fonte isolando eventuali errori e producendo il record diagnostico."""
        url = str(fonte.get('url') or '').strip()
        if not url:
            return '', [], {}

        nome = fonte.get('nome', 'Fonte')
        abilitata = fonte.get('abilitata', True)
        if not abilitata:
            return url, [], {
                "stato": "DISABILITATA",
                "semaforo": "⚪",
                "articoli": 0,
                "ora": "",
                "ultimo_errore": "",
            }

        try:
            notizie = self.scarica_fonte(fonte)
            ora_roma = datetime.datetime.now(tz).strftime('%H:%M')
            return url, notizie, {
                "stato": "OK",
                "semaforo": "🟢",
                "articoli": len(notizie),
                "ora": ora_roma,
                "ultimo_errore": "",
            }
        except Exception as e:
            ora_roma = datetime.datetime.now(tz).strftime('%H:%M')
            stato_err = self.classifica_errore_fonte(e)
            logging.warning(f"⚠️ Errore recupero news da {nome} ({url}): {e}")
            return url, [], {
                "stato": stato_err,
                "semaforo": "🔴",
                "articoli": 0,
                "ora": ora_roma,
                "ultimo_errore": str(e),
            }

    def aggiorna_fonte(self, fonte: dict, tz_roma=None) -> tuple[list[dict], dict]:
        """Aggiorna singola fonte e ne memorizza lo stato semaforico in self.diagnostica."""
        tz = tz_roma or TZ_ROMA
        url, notizie, info = self._valuta_fonte(fonte, tz)
        if url:
            with self._lock:
                self.diagnostica[url] = dict(info)
        return notizie, info

    def aggiorna(self, fonti_override=None, tz_roma=None) -> list[dict]:
        """Aggiorna tutte le fonti, esegue l'interleaving pesato e aggiorna RAM atomicamente."""
        tz = tz_roma or TZ_ROMA
        if fonti_override is not None:
            fonti_da_leggere = list(fonti_override)
        else:
            with self._lock:
                fonti_da_leggere = list(self.fonti)

        notizie_per_fonte = []
        nuova_diagnostica = {}

        for fonte in fonti_da_leggere:
            url, notizie, info = self._valuta_fonte(fonte, tz)
            if not url:
                continue
            nuova_diagnostica[url] = info
            if notizie:
                peso = self.normalizza_peso(fonte.get('peso', 1))
                notizie_per_fonte.append({'notizie': notizie, 'peso': peso})

        notizie_estratte = []
        if notizie_per_fonte:
            ancora_notizie = True
            indici = [0] * len(notizie_per_fonte)
            while ancora_notizie:
                ancora_notizie = False
                for i, f in enumerate(notizie_per_fonte):
                    peso = f['peso']
                    notizie = f['notizie']
                    idx = indici[i]
                    for _ in range(peso):
                        if idx < len(notizie):
                            notizie_estratte.append(notizie[idx])
                            idx += 1
                            indici[i] = idx
                            ancora_notizie = True

        with self._lock:
            self.memoria_news = notizie_estratte
            self.diagnostica = nuova_diagnostica
            self.ultimo_aggiornamento = time.time()

        return [dict(n) for n in notizie_estratte]

    def get_news(self) -> list[dict]:
        """Restituisce copia difensiva thread-safe delle notizie in RAM."""
        with self._lock:
            return [dict(n) for n in self.memoria_news]

    def get_diagnostica(self) -> dict[str, dict]:
        """Restituisce copia difensiva thread-safe della diagnostica per fonte."""
        with self._lock:
            return {k: dict(v) for k, v in self.diagnostica.items()}
