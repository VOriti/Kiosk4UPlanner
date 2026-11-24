#!/usr/bin/env python3
import json
import os
import logging
import time
import threading
import datetime
import requests
import yaml
import hashlib
import hmac
import ipaddress
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import contextlib
import socket
import socketserver
import ssl
import copy
import re
import math
import xml.etree.ElementTree as ET

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

class KioskHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Ignora disconnessioni fisiologiche dei client remoti o bot scanner internet
        exc = sys.exception() if hasattr(sys, 'exception') else sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError)):
            return
        super().handle_error(request, client_address)


PERCORSO_BASE = os.path.dirname(os.path.abspath(__file__))
if PERCORSO_BASE not in sys.path:
    sys.path.insert(0, PERCORSO_BASE)

from core.building_context import (
    ESTENSIONI_LOCANDINE,
    BuildingContext,
    chiave_ordinamento_naturale,
    rileva_formato_immagine,
)
from core.cineca_client import (
    AVVISI_DI_STATO,
    LIMITE_EVENTI_CINECA,
    SOGLIA_ASSENZE_ANNULLAMENTO,
    CinecaClient,
    get_giorno_operativo,
    get_tz_roma,
    sanitize_id_str,
)
from core.news_engine import TIMEOUT_FONTE_SEC, NewsEngine

FILE_CONFIG = os.path.join(PERCORSO_BASE, 'config.yaml')

CONFIG = {}
lock_config = threading.Lock()
SESSIONS = {}
LOGIN_ATTEMPTS = {}
lock_login = threading.Lock()
AVVIO_PROCESSO = time.time()
ultimo_sync_cineca_ok = None
memoria_dati = []
lock_memoria = threading.Lock()
token_cineca = None
storico_impegni = {}
data_storico = None
ultimo_reset_data = None
ultimo_stato_json_salvato = None
ultimo_aggiornamento_preservato = False
memoria_news = []
news_poll_event = threading.Event()

LIMITE_UPLOAD_LOCANDINA = 10 * 1024 * 1024
LIMITE_POST_JSON = 1 * 1024 * 1024

MAX_CONCURRENT_REQUESTS = 40
HTTP_REQUEST_TIMEOUT = 15.0
HTTP_CONCURRENCY_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SEC = 600
SLIDING_WINDOW_SEC = 900

CONFIG_WHITELIST = {
    'main': {'porta_server', 'file_log', 'debug_mode', 'percorso_base'},
    'sicurezza': {'admin_attivo', 'admin_ip_autorizzati'},
    'https': {'abilitato', 'porta_https', 'file_certificato', 'file_chiave', 'forza_redirect_http'},
    'api_cineca': {
        'username', 'password', 'realm', 'id_edificio',
        'anno_accademico_id', 'contesto_id', 'intervallo_aggiornamento_sec', 'url_base',
    },
    'frontend': {
        'mostra_confermati', 'caroselloAttivo', 'titoloSede', 'urlLogo', 'mostraStatoPC',
        'messaggioNessunaLezione', 'messaggioErroreRete', 'pausaTraCaroselli',
        'esposizioneLocandina', 'quotaCarosello', 'intervalloAggiornamento',
        'urlCalendario', 'urlRepo', 'urlLicenza', 'autore', 'emailAutore',
    },
    'footer_news': {
        'abilitato', 'stile_scorrimento', 'velocita', 'colore_testo', 'colore_sfondo',
        'colore_btn', 'dimensione_testo', 'alert_fisso_attivo', 'alert_testo', 'fonti',
    },
}
FONTI_WHITELIST = {'abilitata', 'nome', 'url', 'tipo', 'visibile_di_default', 'peso'}
RE_FILE_LOG_SICURO = re.compile(r'^[a-zA-Z0-9_\-\.]+\.log$')
RE_NOME_CERT_SICURO = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "style-src 'self'; frame-ancestors 'self'"
)

lock_locandine = threading.RLock()


def cartella_locandine():
    return ctx.cartella_locandine()


def percorso_ordine():
    return ctx.percorso_ordine()


def leggi_ordine():
    return ctx.leggi_ordine()


def scrivi_ordine(nomi):
    return ctx.scrivi_ordine(nomi)


def elenco_locandine_ordinato():
    """Ordine di ordine.json, poi i file non elencati in ordine naturale; voci senza file ignorate."""
    return ctx.elenco_locandine_ordinato()


def elenco_file_locandine():
    return ctx.elenco_file_locandine()


def pulisci_upload_orfani():
    return ctx.pulisci_upload_orfani()


def salva_locandina_da_stream(rfile, lunghezza):
    """Scrive il body su .tmp a blocchi, valida i magic bytes e rinomina con un nome immutabile."""
    return ctx.salva_locandina_da_stream(rfile, lunghezza)


def salva_stato(forza=False):
    """Salva lo stato degli impegni in modo condizionale e atomico fuori da lock_memoria (ST-09)."""
    global ultimo_stato_json_salvato
    esito = ctx.salva_stato(forza=forza)
    ultimo_stato_json_salvato = ctx.ultimo_stato_json_salvato
    return esito


def verifica_e_esegui_reset_04am(dt_roma=None):
    """Verifica ed esegue il reset programmato alle 04:00 AM (o catch-up all'avvio) con ST-11.1."""
    global memoria_dati, ultimo_reset_data, ultimo_stato_json_salvato
    esito = ctx.verifica_e_esegui_reset_04am(dt_roma=dt_roma)
    if esito:
        memoria_dati = ctx.ottieni_dati_pubblici()
    ultimo_reset_data = ctx.ultimo_reset_data
    ultimo_stato_json_salvato = ctx.ultimo_stato_json_salvato
    return esito

DEFAULT_CONFIG = """main:
  porta_server: 8080
  percorso_base: '{PERCORSO}'
  file_log: 'kiosk.log'
  # ----------------------------------------------------------------------------
  # MODALITÀ DEBUG E DIAGNOSTICA
  # ----------------------------------------------------------------------------
  # Imposta su 'true' solo in fase di test o se richiesto dall'assistenza.
  debug_mode: false
sicurezza:
  admin_attivo: true
  admin_ip_autorizzati:
    - '127.0.0.1'
  password_admin_hash: 'a45090e56b7639cae365ee553d321fe8ef76300adcab875a064bb3f0abbc08d0'
https:
  abilitato: false
  porta_https: 8443
  file_certificato: 'cert.pem'
  file_chiave: 'key.pem'
  forza_redirect_http: false
api_cineca:
  username: ''
  password: ''
  realm: ''
  id_edificio: ''
  anno_accademico_id: ''
  contesto_id: ''
  intervallo_aggiornamento_sec: 300
  url_base: 'https://cineca.prod.up.cineca.it/api'
frontend:
  mostra_confermati: true
  caroselloAttivo: true
  titoloSede: 'Impegni Aule'
  urlLogo: './logo.png'
  mostraStatoPC: true
  messaggioNessunaLezione: 'Nessun impegno attivo programmato per la giornata.'
  messaggioErroreRete: 'Connessione persa col Server API. Tentativo di riconnessione...'
  pausaTraCaroselli: 180000
  esposizioneLocandina: 10000
  quotaCarosello: 0.30
  intervalloAggiornamento: 15000
  urlCalendario: ''
  urlRepo: 'https://github.com/VOriti/Kiosk4Uplanner'
  urlLicenza: 'https://creativecommons.org/licenses/by-nc-sa/4.0/deed.it'
  autore: 'Vincenzo Oriti'
  emailAutore: 'vincenzo.oriti@unipv.it'
footer_news:
  abilitato: true
  stile_scorrimento: 'verticale'
  velocita: 20
  colore_testo: '#c9d1d9'
  colore_sfondo: '#3e3c3d'
  dimensione_testo: '1.20rem'
  alert_fisso_attivo: false
  alert_testo: ''
  fonti: []
"""

def load_config():
    global CONFIG, PERCORSO_BASE
    if not os.path.exists(FILE_CONFIG):
        with open(FILE_CONFIG, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_CONFIG.replace('{PERCORSO}', PERCORSO_BASE))
    with open(FILE_CONFIG, 'r', encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f) or {}
        
    if isinstance(CONFIG, dict) and 'main' in CONFIG and isinstance(CONFIG['main'], dict) and 'percorso_base' in CONFIG['main']:
        pb = str(CONFIG['main']['percorso_base'] or '').strip("'\"")
        if os.path.exists(pb):
            PERCORSO_BASE = pb

load_config()


def _crea_cineca_client():
    api_cfg = CONFIG.get('api_cineca', {}) if isinstance(CONFIG, dict) else {}
    return CinecaClient(
        url_base=api_cfg.get('url_base') or 'https://cineca.prod.up.cineca.it/api',
        realm=sanitize_id_str(api_cfg.get('realm')),
        username=api_cfg.get('username', ''),
        password=api_cfg.get('password', ''),
        timeout=15,
    )


cineca_client = _crea_cineca_client()
news_engine = NewsEngine(CONFIG.get('footer_news', {}).get('fonti', []))
server_https_attivo = False

import logging.handlers

file_log = os.path.join(PERCORSO_BASE, CONFIG.get('main', {}).get('file_log', 'kiosk.log'))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

handler_rotativo = logging.handlers.RotatingFileHandler(
    file_log,
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=4,              # 4 file di backup (.1 .. .4) per un totale massimo di 50 MB
    encoding='utf-8'
)
handler_rotativo.setFormatter(logging.Formatter(
    fmt='%(asctime)s - [API SERVER] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
root_logger.addHandler(handler_rotativo)

ctx = BuildingContext(CONFIG, PERCORSO_BASE)
lock_config = ctx.lock_config
lock_memoria = ctx.lock_memoria
lock_locandine = ctx.lock_locandine
storico_impegni = ctx.storico_impegni


def carica_stato():
    global ultimo_reset_data, ultimo_stato_json_salvato
    ctx.carica_stato()
    tz_roma = get_tz_roma()
    now_roma = datetime.datetime.now(tz_roma)

    # Catch-up delle 04:00 AM all'avvio (es. accensione portineria alle 07:30):
    if ctx.verifica_e_esegui_reset_04am(now_roma):
        logging.info("🧹 Catch-up avvio: storico impegni resettato per la nuova giornata operativa.")
    else:
        # Se siamo nella stessa giornata operativa, rimuoviamo solo eventuali eventi scaduti in-place
        dt_inizio_giorno = datetime.datetime.combine(
            get_giorno_operativo(now_roma), datetime.time(0, 0, 0), tzinfo=tz_roma
        )
        mezzanotte_ts = dt_inizio_giorno.timestamp()
        with ctx.lock_memoria:
            chiavi_scadute = [
                k for k, v in ctx.storico_impegni.items()
                if v.get('timestamp_fine', 0) <= mezzanotte_ts
            ]
            for k in chiavi_scadute:
                del ctx.storico_impegni[k]

    ultimo_reset_data = ctx.ultimo_reset_data
    ultimo_stato_json_salvato = ctx.ultimo_stato_json_salvato


carica_stato()

def salva_config_yaml(file_path=None, config_data=None):
    """Salva il dizionario di configurazione preservando commenti e struttura YAML."""
    if file_path is None:
        file_path = FILE_CONFIG
    if config_data is None:
        config_data = CONFIG
    import re
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    out_lines = []
    curr_sec = None
    skip_list = False
    list_indent_len = 0
    seen_keys = set()
    seen_secs = set()
    for line in lines:
        if skip_list:
            stripped = line.strip()
            line_indent = len(line) - len(line.lstrip(' '))
            if stripped == '' or line_indent > list_indent_len:
                continue
            else:
                skip_list = False
        
        m_sec = re.match(r'^([a-zA-Z0-9_]+):', line)
        if m_sec:
            if curr_sec and curr_sec in config_data and isinstance(config_data[curr_sec], dict):
                for k, v in config_data[curr_sec].items():
                    if k not in seen_keys:
                        if isinstance(v, list):
                            if not v:
                                out_lines.append(f"  {k}: []\n")
                            else:
                                out_lines.append(f"  {k}:\n")
                                for item in v:
                                    if isinstance(item, dict):
                                        out_lines.append(f"    - nome: {json.dumps(item.get('nome', ''))}\n")
                                        out_lines.append(f"      url: {json.dumps(item.get('url', ''))}\n")
                                        out_lines.append(f"      tipo: {json.dumps(item.get('tipo', 'rss'))}\n")
                                        abilitata_str = 'true' if item.get('abilitata', True) else 'false'
                                        out_lines.append(f"      abilitata: {abilitata_str}\n")
                                        visibile_str = 'true' if item.get('visibile_di_default', True) else 'false'
                                        out_lines.append(f"      visibile_di_default: {visibile_str}\n")
                                        out_lines.append(f"      peso: {item.get('peso', 1)}\n")
                                    else:
                                        out_lines.append(f"    - {json.dumps(item)}\n")
                        elif not isinstance(v, dict):
                            out_lines.append(f"  {k}: {json.dumps(v)}\n")
            curr_sec = m_sec.group(1)
            seen_secs.add(curr_sec)
            seen_keys = set()
            out_lines.append(line)
            continue
        
        if curr_sec and curr_sec in config_data:
            m_key = re.match(r'^(\s+)([a-zA-Z0-9_]+):\s*(.*)', line)
            if m_key:
                indent, key, resto = m_key.group(1), m_key.group(2), m_key.group(3)
                seen_keys.add(key)
                if key in config_data[curr_sec]:
                    val = config_data[curr_sec][key]
                    comm = ""
                    idx = resto.find('#')
                    while idx != -1:
                        if resto.count('"', 0, idx) % 2 == 0 and resto.count("'", 0, idx) % 2 == 0:
                            comm = " " + resto[idx:]
                            break
                        idx = resto.find('#', idx + 1)
                    
                    if isinstance(val, bool):
                        v_str = 'true' if val else 'false'
                        out_lines.append(f"{indent}{key}: {v_str}{comm}\n")
                    elif isinstance(val, list):
                        skip_list = True
                        list_indent_len = len(indent)
                        if not val:
                            out_lines.append(f"{indent}{key}: []{comm}\n")
                        else:
                            out_lines.append(f"{indent}{key}:{comm}\n")
                            for item in val:
                                if isinstance(item, dict):
                                    out_lines.append(f"{indent}  - nome: {json.dumps(item.get('nome', ''))}\n")
                                    out_lines.append(f"{indent}    url: {json.dumps(item.get('url', ''))}\n")
                                    out_lines.append(f"{indent}    tipo: {json.dumps(item.get('tipo', 'rss'))}\n")
                                    abilitata_str = 'true' if item.get('abilitata', True) else 'false'
                                    out_lines.append(f"{indent}    abilitata: {abilitata_str}\n")
                                    visibile_str = 'true' if item.get('visibile_di_default', True) else 'false'
                                    out_lines.append(f"{indent}    visibile_di_default: {visibile_str}\n")
                                    out_lines.append(f"{indent}    peso: {item.get('peso', 1)}\n")
                                else:
                                    out_lines.append(f"{indent}  - {json.dumps(item)}\n")
                    else:
                        v_str = json.dumps(val)
                        out_lines.append(f"{indent}{key}: {v_str}{comm}\n")
                    continue
        out_lines.append(line)
    if curr_sec and curr_sec in config_data and isinstance(config_data[curr_sec], dict):
        for k, v in config_data[curr_sec].items():
            if k not in seen_keys:
                if isinstance(v, list):
                    if not v:
                        out_lines.append(f"  {k}: []\n")
                    else:
                        out_lines.append(f"  {k}:\n")
                        for item in v:
                            if isinstance(item, dict):
                                out_lines.append(f"    - nome: {json.dumps(item.get('nome', ''))}\n")
                                out_lines.append(f"      url: {json.dumps(item.get('url', ''))}\n")
                                out_lines.append(f"      tipo: {json.dumps(item.get('tipo', 'rss'))}\n")
                                abilitata_str = 'true' if item.get('abilitata', True) else 'false'
                                out_lines.append(f"      abilitata: {abilitata_str}\n")
                            else:
                                out_lines.append(f"    - {json.dumps(item)}\n")
                elif not isinstance(v, dict):
                    out_lines.append(f"  {k}: {json.dumps(v)}\n")
    for sec, sec_val in config_data.items():
        if sec not in seen_secs and isinstance(sec_val, dict):
            out_lines.append(f"\n{sec}:\n")
            for k, v in sec_val.items():
                if isinstance(v, bool):
                    v_str = 'true' if v else 'false'
                    out_lines.append(f"  {k}: {v_str}\n")
                elif isinstance(v, list):
                    if not v:
                        out_lines.append(f"  {k}: []\n")
                    else:
                        out_lines.append(f"  {k}:\n")
                        for item in v:
                            out_lines.append(f"    - {json.dumps(item)}\n")
                elif not isinstance(v, dict):
                    out_lines.append(f"  {k}: {json.dumps(v)}\n")
    file_tmp = f"{file_path}.tmp"
    with open(file_tmp, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)
        f.flush()
        os.fsync(f.fileno())
    os.replace(file_tmp, file_path)

def effettua_login():
    global token_cineca
    api_cineca = CONFIG.get('api_cineca', {})
    cineca_client.url_base = str(api_cineca.get('url_base') or 'https://cineca.prod.up.cineca.it/api').strip().rstrip('/')
    cineca_client.realm = sanitize_id_str(api_cineca.get('realm'))
    cineca_client.username = str(api_cineca.get('username', ''))
    cineca_client.password = str(api_cineca.get('password', ''))
    token_cineca = cineca_client.login()
    return bool(token_cineca)


def estrai_e_formatta_dati(impegni_grezzi):
    global data_storico, ultimo_aggiornamento_preservato
    tz_roma = get_tz_roma()
    ora_attuale = datetime.datetime.now(tz_roma)
    oggi_str = str(get_giorno_operativo(ora_attuale))
    if oggi_str != data_storico:
        data_storico = oggi_str
    id_edificio = sanitize_id_str(CONFIG.get('api_cineca', {}).get('id_edificio'))
    mostra_confermati = CONFIG.get('frontend', {}).get('mostra_confermati', True)
    with ctx.lock_memoria:
        dati_puliti, ultimo_aggiornamento_preservato = CinecaClient.processa_impegni(
            impegni_grezzi,
            ctx.storico_impegni,
            id_edificio=id_edificio,
            mostra_confermati=mostra_confermati,
            ora_attuale=ora_attuale,
        )
        ctx.ultimo_aggiornamento_preservato = ultimo_aggiornamento_preservato
    salva_stato()
    return dati_puliti


def verifica_sentinella_limite(dati_grezzi):
    """Segnala nel log una risposta CINECA arrivata al tetto 'limit' (possibile troncatura)."""
    return CinecaClient.verifica_sentinella_limite(dati_grezzi)

def intervallo_aggiornamento_sec():
    try:
        intervallo = int(CONFIG.get('api_cineca', {}).get('intervallo_aggiornamento_sec') or 300)
        return intervallo if intervallo > 0 else 300
    except (ValueError, TypeError):
        return 300

def elabora_risposta_cineca(dati_grezzi):
    global memoria_dati, ultimo_sync_cineca_ok
    verifica_sentinella_limite(dati_grezzi)
    dati_puliti = estrai_e_formatta_dati(dati_grezzi)
    ctx.aggiorna_impegni(ctx.storico_impegni, nuovi_dati=dati_puliti)
    with lock_memoria:
        memoria_dati = ctx.memoria_dati
    ultimo_sync_cineca_ok = time.time()
    ctx.ultimo_sync_cineca_ok = ultimo_sync_cineca_ok
    ctx.ultimo_aggiornamento_preservato = ultimo_aggiornamento_preservato
    if ultimo_aggiornamento_preservato:
        logging.info(f"🛡️ Nessun nuovo dato CINECA: {len(memoria_dati)} impegni precedenti mantenuti a video.")
    else:
        logging.info(f"✅ Dati ricevuti da CINECA! Trovati {len(memoria_dati)} impegni.")

def ciclo_aggiornamento_api():
    global token_cineca, memoria_dati
    logging.info("🚀 Avviato demone API CINECA (Modalità Admin Autenticata).")
    
    while True:
        try:
            api_cineca = CONFIG.get('api_cineca', {})
            realm = sanitize_id_str(api_cineca.get('realm'))
            url_base = str(api_cineca.get('url_base') or 'https://cineca.prod.up.cineca.it/api').strip().rstrip('/')
            url_impegni = f"{url_base}/Impegni/getImpegniCalendario"
            intervallo = intervallo_aggiornamento_sec()
            
            if not token_cineca:
                if not effettua_login():
                    time.sleep(60)
                    continue
            
            headers = { 
                "Authorization": token_cineca,
                "Content-Type": "application/json",
                "X-Realm": realm 
            }            
            
            tz_roma = get_tz_roma()
            now_roma = datetime.datetime.now(tz_roma)

            # Controllo reset programmato alle 04:00 AM (o catch-up)
            if verifica_e_esegui_reset_04am(now_roma):
                logging.info("🌅 Eseguito reset delle 04:00 AM. Avvio scaricamento orari fresco.")

            giorno_op = get_giorno_operativo(now_roma)
            dt_inizio_roma = datetime.datetime.combine(giorno_op, datetime.time(0, 0, 0), tzinfo=tz_roma)
            dt_fine_roma = datetime.datetime.combine(giorno_op, datetime.time(23, 59, 59), tzinfo=tz_roma)

            inizio_giornata = dt_inizio_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            fine_giornata = dt_fine_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            payload = {
                "limit": LIMITE_EVENTI_CINECA,
                "dataInizio": inizio_giornata,
                "dataFine": fine_giornata,
                "mostraImpegniSenzaAula": False,
                "nascondiIndisponibilitaParziali": False
            }
            
            anno_id = sanitize_id_str(api_cineca.get('anno_accademico_id'))
            if anno_id:
                payload["annoAccademicoId"] = anno_id
                
            contesto_id = sanitize_id_str(api_cineca.get('contesto_id'))
            if contesto_id:
                payload["contestoId"] = contesto_id

            
            is_debug = bool(CONFIG.get('main', {}).get('debug_mode', False))
            if is_debug:
                logging.info(f"🕵️ DEBUG: Richiesta impegni a {url_impegni} (Payload: {payload})")
            
            risposta = requests.post(url_impegni, json=payload, headers=headers, timeout=15)
            
            if risposta.status_code == 401:
                logging.error("❌ Token scaduto o non valido (401). Forzo il rinnovo.")
                token_cineca = None
                cineca_client.invalida_token()
                time.sleep(2)
                continue
            elif risposta.status_code == 200:
                cineca_client.reset_backoff()
                dati_grezzi = risposta.json()
                if is_debug:
                    logging.info(f"🕵️ DEBUG: Ricevuti {len(dati_grezzi)} impegni grezzi.")
                    edifici_scoperti = set()
                    for imp in dati_grezzi:
                        for a in imp.get('aule', []):
                            if isinstance(a, dict):
                                ed = a.get('edificio', {})
                                if isinstance(ed, dict) and ed.get('codice'):
                                    desc = ed.get('descrizione') or 'Nessuna descrizione'
                                    edifici_scoperti.add(f"Codice '{ed.get('codice')}': {desc}")
                    if edifici_scoperti:
                        logging.info(f"🕵️ DEBUG MAPPA EDIFICI RILEVATI ({len(edifici_scoperti)}): {sorted(list(edifici_scoperti))}")
                    else:
                        logging.info("🕵️ DEBUG MAPPA EDIFICI: Nessun edificio rilevato negli impegni grezzi ricevuti.")
                elabora_risposta_cineca(dati_grezzi)
            else:
                logging.error(f"❌ Errore HTTP {risposta.status_code}: {risposta.text[:100]}")
                
        except Exception as e:
            logging.error(f"❌ Errore critico nel ciclo API: {e}")
        
        intervallo = intervallo_aggiornamento_sec()
        time.sleep(intervallo)

DIAGNOSTICA_NEWS = {}   # url -> {"stato", "semaforo", "articoli", "ora", "ultimo_errore"}; sostituito per intero a ogni giro
TIMEOUT_FONTE_NEWS_SEC = TIMEOUT_FONTE_SEC

classifica_errore_fonte = NewsEngine.classifica_errore_fonte
clean_html = NewsEngine.clean_html
parse_data_notizia = NewsEngine.parse_data_notizia
normalizza_peso = NewsEngine.normalizza_peso


def scarica_fonte(fonte):
    return news_engine.scarica_fonte(fonte)


def aggiorna_news_una_volta():
    global memoria_news, DIAGNOSTICA_NEWS
    footer_config = CONFIG.get('footer_news', {})
    fonti = footer_config.get('fonti', [])
    news_engine.set_fonti(fonti)
    notizie_estratte = news_engine.aggiorna()
    DIAGNOSTICA_NEWS = news_engine.get_diagnostica()
    memoria_news = notizie_estratte

def NewsPollingDaemon():
    logging.info("🚀 Avviato demone News (Footer).")
    while True:
        try:
            footer_config = CONFIG.get('footer_news', {})
            if footer_config.get('abilitato', False):
                aggiorna_news_una_volta()
        except Exception as e:
            logging.error(f"❌ Errore critico demone News: {e}")

        news_poll_event.wait(3600)
        news_poll_event.clear()

HASH_PASSWORD_DEFAULT = frozenset({
    '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918',
    '737a5c64f7f67b7f86e6b6b96698eb5d24b85ba933dd2710b867e16b6b6b9669',
    'a45090e56b7639cae365ee553d321fe8ef76300adcab875a064bb3f0abbc08d0',
})

def password_default_bloccata(client_ip, hash_salvato):
    """True se l'hash è di default e la richiesta non arriva da loopback."""
    if hash_salvato not in HASH_PASSWORD_DEFAULT:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
        ip = getattr(ip, 'ipv4_mapped', None) or ip
        return not ip.is_loopback
    except ValueError:
        return True


def verifica_login_admin(client_ip, password_proposta, hash_corretto, now_ts=None):
    """Controllo lockout, confronto HMAC a tempo costante e incremento atomico sotto un unico lock_login (ST-10.3)."""
    ts = time.time() if now_ts is None else float(now_ts)
    pwd_str = password_proposta if isinstance(password_proposta, str) else ''
    pwd_hash = hashlib.sha256(pwd_str.encode('utf-8')).hexdigest()

    with lock_login:
        ip_scaduti = [
            ip for ip, rec in LOGIN_ATTEMPTS.items()
            if (ts - rec.get('ultimo_tentativo', ts) > 3600) and (rec.get('locked_until', 0) <= ts)
        ]
        for ip in ip_scaduti:
            del LOGIN_ATTEMPTS[ip]

        record = LOGIN_ATTEMPTS.get(client_ip)
        if record is None:
            record = {'count': 0, 'locked_until': 0, 'ultimo_tentativo': ts}

        locked_until = record.get('locked_until', 0)
        if locked_until > ts:
            secondi_attesa = max(1, int(locked_until - ts))
            return {
                'status': 429,
                'retry_after': secondi_attesa,
                'secondi_attesa': secondi_attesa,
                'token': None,
            }

        ultimo = record.get('ultimo_tentativo', ts)
        if (0 < locked_until <= ts) or (ts - ultimo > SLIDING_WINDOW_SEC):
            record['count'] = 0
            record['locked_until'] = 0

        if hmac.compare_digest(pwd_hash, str(hash_corretto or '')):
            LOGIN_ATTEMPTS.pop(client_ip, None)
            token = secrets.token_hex(16)
            SESSIONS[token] = time.time() + 3600
            return {
                'status': 200,
                'retry_after': 0,
                'secondi_attesa': 0,
                'token': token,
            }

        record['count'] = record.get('count', 0) + 1
        record['ultimo_tentativo'] = ts
        if record['count'] >= MAX_LOGIN_ATTEMPTS:
            record['locked_until'] = ts + LOCKOUT_DURATION_SEC
            logging.warning(
                f"🚨 Troppi tentativi di login errati dall'IP {client_ip}. IP bloccato per 10 minuti."
            )
        LOGIN_ATTEMPTS[client_ip] = record
        return {
            'status': 401,
            'retry_after': 0,
            'secondi_attesa': 0,
            'token': None,
        }


def _valida_porta(valore, nome_campo):
    if isinstance(valore, bool):
        raise ValueError(f"Valore non consentito per {nome_campo}")
    if isinstance(valore, int):
        porta = valore
    elif isinstance(valore, str) and valore.strip().isdigit():
        porta = int(valore.strip())
    else:
        raise ValueError(f"Valore non consentito per {nome_campo}: attesa porta numerica 1-65535")
    if not (1 <= porta <= 65535):
        raise ValueError(f"Porta {nome_campo} fuori intervallo consentito (1-65535)")
    return porta


def _valida_nome_file_sicuro(valore, pattern, nome_campo):
    if not isinstance(valore, str) or not valore.strip():
        raise ValueError(f"Nome file non consentito per {nome_campo}")
    v = valore.strip()
    if (
        '..' in v
        or '/' in v
        or '\\' in v
        or '\x00' in v
        or os.path.isabs(v)
        or not pattern.match(v)
    ):
        raise ValueError(f"Percorso o nome file non consentito per {nome_campo}")
    return v


def valida_payload_admin_save(payload, config_attuale=None):
    """Validazione rigorosa a whitelist esplicita per POST /api/admin/save (N-10)."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Payload configurazione non consentito o vuoto")

    chiavi_top_ammesse = set(CONFIG_WHITELIST) | {'admin_password'}
    extra_top = set(payload.keys()) - chiavi_top_ammesse
    if extra_top:
        raise ValueError(f"Sezioni configurazione non consentite: {sorted(extra_top)}")

    if 'admin_password' in payload and not isinstance(payload['admin_password'], str):
        raise ValueError("Campo admin_password non consentito")

    for sezione, chiavi_ammesse in CONFIG_WHITELIST.items():
        if sezione not in payload:
            continue
        val_sez = payload[sezione]
        if not isinstance(val_sez, dict):
            raise ValueError(f"Sezione '{sezione}' non consentita: atteso oggetto JSON")
        extra_keys = set(val_sez.keys()) - chiavi_ammesse
        if extra_keys:
            raise ValueError(f"Chiavi non consentite nella sezione '{sezione}': {sorted(extra_keys)}")

    if 'main' in payload:
        main_cfg = payload['main']
        if 'percorso_base' in main_cfg:
            pb_raw = main_cfg['percorso_base']
            if pb_raw is not None and not isinstance(pb_raw, str):
                raise ValueError("Modifica di percorso_base non consentita via API")
            pb_attuale = str((config_attuale or {}).get('main', {}).get('percorso_base', '') or '').strip("'\"")
            pb_nuovo = str(pb_raw or '').strip("'\"")
            if pb_nuovo not in ('', pb_attuale):
                raise ValueError("Modifica di percorso_base non consentita via API")
            del main_cfg['percorso_base']
        if 'file_log' in main_cfg:
            main_cfg['file_log'] = _valida_nome_file_sicuro(main_cfg['file_log'], RE_FILE_LOG_SICURO, 'file_log')
        if 'porta_server' in main_cfg:
            main_cfg['porta_server'] = _valida_porta(main_cfg['porta_server'], 'porta_server')

    if 'https' in payload:
        https_cfg = payload['https']
        if 'porta_https' in https_cfg:
            https_cfg['porta_https'] = _valida_porta(https_cfg['porta_https'], 'porta_https')
        if 'file_certificato' in https_cfg:
            https_cfg['file_certificato'] = _valida_nome_file_sicuro(
                https_cfg['file_certificato'], RE_NOME_CERT_SICURO, 'file_certificato'
            )
        if 'file_chiave' in https_cfg:
            https_cfg['file_chiave'] = _valida_nome_file_sicuro(
                https_cfg['file_chiave'], RE_NOME_CERT_SICURO, 'file_chiave'
            )

    if 'sicurezza' in payload:
        sic_cfg = payload['sicurezza']
        if 'admin_ip_autorizzati' in sic_cfg:
            ips = sic_cfg['admin_ip_autorizzati']
            if not isinstance(ips, list) or not all(isinstance(ip, str) for ip in ips):
                raise ValueError("Campo 'admin_ip_autorizzati' non consentito: attesa lista di stringhe")

    if 'footer_news' in payload:
        fn_cfg = payload['footer_news']
        if 'fonti' in fn_cfg:
            fonti = fn_cfg['fonti']
            if not isinstance(fonti, list) or len(fonti) > 6:
                raise ValueError("Campo 'fonti' non consentito: attesa lista di al massimo 6 fonti")
            for idx, fonte in enumerate(fonti):
                if not isinstance(fonte, dict):
                    raise ValueError(f"Fonte news #{idx + 1} non consentita: atteso oggetto JSON")
                extra_f = set(fonte.keys()) - FONTI_WHITELIST
                if extra_f:
                    raise ValueError(
                        f"Chiavi non consentite nella fonte news #{idx + 1}: {sorted(extra_f)}"
                    )

    return payload


class KioskServer(BaseHTTPRequestHandler):
    timeout = HTTP_REQUEST_TIMEOUT

    def setup(self):
        self.timeout = HTTP_REQUEST_TIMEOUT
        super().setup()

    def handle(self):
        acquired = HTTP_CONCURRENCY_SEMAPHORE.acquire(blocking=False)
        if not acquired:
            corpo_503 = json.dumps({
                'success': False,
                'error': 'Server sovraccarico: limite concorrenza raggiunto',
            }).encode('utf-8')
            risposta_503 = (
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Type: application/json\r\n"
                b"Retry-After: 5\r\n"
                b"Connection: close\r\n"
                b"Content-Length: " + str(len(corpo_503)).encode('ascii') + b"\r\n\r\n" + corpo_503
            )
            try:
                self.wfile.write(risposta_503)
                self.wfile.flush()
                # Lingering close (RFC 7230 §6.6): segnala EOF in scrittura e drena i byte in arrivo
                # per evitare che socket.close() generi TCP RST prima che il client legga il 503.
                with contextlib.suppress(OSError):
                    self.connection.shutdown(socket.SHUT_WR)
                self.connection.settimeout(0.05)
                drenati = 0
                while drenati < 16384:
                    try:
                        chunk = self.connection.recv(4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    drenati += len(chunk)
            except OSError:
                pass
            return
        try:
            super().handle()
        finally:
            HTTP_CONCURRENCY_SEMAPHORE.release()

    def log_message(self, format, *args): pass 

    def end_headers(self):
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', CONTENT_SECURITY_POLICY)
        super().end_headers() 
    
    def _check_security(self):
        sicurezza = CONFIG.get('sicurezza', {})
        if not sicurezza.get('admin_attivo', False):
            self.send_error(404, "Not Found")
            return False
        
        client_ip = self.client_address[0]
        allowed_ips = sicurezza.get('admin_ip_autorizzati', [])
        
        if not allowed_ips:
            return True
            
        is_allowed = False
        try:
            ip_obj = ipaddress.ip_address(client_ip)
            for cidr in allowed_ips:
                if ip_obj in ipaddress.ip_network(cidr, strict=False):
                    is_allowed = True
                    break
        except Exception:
            pass
            
        if not is_allowed:
            self.send_error(403, "Forbidden")
            return False
            
        return True

    def _check_token(self):
        token = self.headers.get('X-Admin-Token')
        valido = True
        if not token or token not in SESSIONS:
            valido = False
        elif SESSIONS[token] < time.time():
            del SESSIONS[token]
            valido = False

        if not valido:
            try:
                cl = int(self.headers.get('Content-Length', '0'))
                if cl > 0:
                    self.rfile.read(min(cl, 65536))
            except Exception:
                pass
            self.send_error(401, "Unauthorized")
            return False
        return True

    def _invia_json(self, codice, oggetto):
        self.send_response(codice)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(oggetto).encode('utf-8'))

    def _leggi_content_length(self, limite):
        """Lunghezza del body, oppure None dopo aver già risposto 400/413. Header assente = 0."""
        grezzo = self.headers.get('Content-Length')
        if grezzo is None:
            return 0
        try:
            n = int(grezzo.strip())
        except ValueError:
            self.send_error(400, "Content-Length non valido")
            return None
        if n < 0:
            self.send_error(400, "Content-Length non valido")
            return None
        if n > limite:
            self.send_error(413, "Payload Too Large")
            return None
        return n
        
    def do_GET(self):
        is_ssl = getattr(self.server, 'is_ssl', False)
        https_cfg = CONFIG.get('https', {})
        if not is_ssl and server_https_attivo and https_cfg.get('forza_redirect_http'):
            host = self.headers.get('Host', '')
            has_explicit_port = ':' in host
            host_clean = host.split(':')[0] if host else 'localhost'
            if host_clean not in ['localhost', '127.0.0.1']:
                porta_https = int(https_cfg.get('porta_https', 8443))
                # Se la richiesta è arrivata sulla porta 80 standard (iptables), reindirizza a 443 standard (senza porta)
                if not has_explicit_port or porta_https == 443:
                    redirect_port = ""
                else:
                    redirect_port = f":{porta_https}"
                target_url = f"https://{host_clean}{redirect_port}{self.path}"
                self.send_response(307)
                self.send_header('Location', target_url)
                self.end_headers()
                return

        parsed_path = self.path.split('?')[0]
        if parsed_path == '/':
            self.serve_file(os.path.join(PERCORSO_BASE, 'remoto.html'), 'text/html; charset=utf-8')
        elif parsed_path == '/remoto.html':
            qs = ('?' + self.path.split('?', 1)[1]) if '?' in self.path else ''
            self.send_response(301)
            self.send_header('Location', '/' + qs)
            self.end_headers()
        elif parsed_path == '/static/remoto.js':
            self.serve_file(os.path.join(PERCORSO_BASE, 'static', 'remoto.js'), 'application/javascript; charset=utf-8')
        elif parsed_path == '/static/remoto.css':
            self.serve_file(os.path.join(PERCORSO_BASE, 'static', 'remoto.css'), 'text/css; charset=utf-8')
        elif parsed_path == '/static/admin.js':
            if self._check_security():
                self.serve_file(os.path.join(PERCORSO_BASE, 'static', 'admin.js'), 'application/javascript; charset=utf-8')
        elif parsed_path == '/static/admin.css':
            if self._check_security():
                self.serve_file(os.path.join(PERCORSO_BASE, 'static', 'admin.css'), 'text/css; charset=utf-8')
        elif parsed_path == '/config_pubblica':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            with lock_config:
                frontend_config = dict(CONFIG.get('frontend', {}))
                footer_news_config = dict(CONFIG.get('footer_news', {}))
            self.wfile.write(json.dumps({**frontend_config, "footer_news": footer_news_config}).encode('utf-8'))
        elif parsed_path == '/api/news':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(memoria_news).encode('utf-8'))
        elif parsed_path == '/dati.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(ctx.ottieni_dati_pubblici()).encode('utf-8'))
        elif parsed_path == '/stato':
            self._invia_json(200, {"ultimo_sync_cineca": ultimo_sync_cineca_ok,
                                   "preservato": ultimo_aggiornamento_preservato,
                                   "ora_server": time.time(), "avvio_server": AVVIO_PROCESSO,
                                   "intervallo_sec": intervallo_aggiornamento_sec()})
        elif parsed_path == '/logo.png': 
            self.serve_file(os.path.join(PERCORSO_BASE, 'logo.png'), 'image/png')
        elif parsed_path.startswith('/locandine/'): 
            nome_file = os.path.basename(parsed_path)
            dir_locandine = os.path.abspath(cartella_locandine())
            percorso_file = os.path.abspath(os.path.join(dir_locandine, nome_file))
            ext = os.path.splitext(nome_file)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp'
            }
            
            # Protezione path traversal, verifica estensione immagine e file reale
            prefix = dir_locandine if dir_locandine.endswith(os.sep) else dir_locandine + os.sep
            if (not percorso_file.startswith(prefix) or 
                ext not in mime_map or 
                not os.path.isfile(percorso_file)):
                self.send_response(404)
                self.end_headers()
                return
            
            self.serve_file(percorso_file, mime_map[ext])
        elif parsed_path == '/lista_locandine.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(elenco_locandine_ordinato()).encode('utf-8'))
        elif parsed_path == '/api/admin/locandine':
            if not self._check_security() or not self._check_token():
                return
            cartella = cartella_locandine()
            voci = []
            for nome in elenco_locandine_ordinato():
                percorso = os.path.join(cartella, nome)
                try:
                    stat = os.stat(percorso)
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = time.time()
                kb = math.ceil(size / 1024)
                dt = datetime.datetime.fromtimestamp(mtime, tz=get_tz_roma())
                voci.append({
                    "nome": nome,
                    "kb": kb,
                    "caricata": dt.strftime("%d/%m/%Y %H:%M")
                })
            self._invia_json(200, voci)
        elif parsed_path == '/admin':
            if self._check_security():
                self.serve_file(os.path.join(PERCORSO_BASE, 'admin.html'), 'text/html; charset=utf-8')
        elif parsed_path == '/api/admin/config_full':
            if self._check_security() and self._check_token():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                with lock_config:
                    safe_config = json.loads(json.dumps(CONFIG))
                safe_config['diagnostica_news'] = dict(DIAGNOSTICA_NEWS)
                if 'api_cineca' in safe_config and 'password' in safe_config['api_cineca']:
                    safe_config['api_cineca']['password'] = '********'
                
                hash_salvato = safe_config.get('sicurezza', {}).get('password_admin_hash', '')
                safe_config['avviso_sicurezza'] = hash_salvato in HASH_PASSWORD_DEFAULT
                    
                self.wfile.write(json.dumps(safe_config).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        global CONFIG
        parsed_path = self.path.split('?')[0]
        limite = LIMITE_UPLOAD_LOCANDINA if parsed_path == '/api/admin/locandine/upload' else LIMITE_POST_JSON
        content_length = self._leggi_content_length(limite)
        if content_length is None:
            return

        if parsed_path == '/api/admin/login':
            if not self._check_security(): return
            
            client_ip = self.client_address[0] if self.client_address else '127.0.0.1'
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    self.send_error(400, "Bad Request")
                    return
                pwd = data.get('password', '')
                if not isinstance(pwd, str):
                    self.send_error(400, "Bad Request")
                    return

                with lock_config:
                    hash_salvato = CONFIG.get('sicurezza', {}).get('password_admin_hash', '')

                esito = verifica_login_admin(client_ip, pwd, hash_salvato)

                if esito['status'] == 200:
                    self._invia_json(200, {"token": esito['token']})
                elif esito['status'] == 429:
                    secondi_attesa = esito['secondi_attesa']
                    self.send_response(429)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Retry-After', str(esito['retry_after']))
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": f"Troppi tentativi falliti. Riprova tra {secondi_attesa} secondi.",
                        "secondi_attesa": secondi_attesa
                    }).encode('utf-8'))
                else:
                    time.sleep(1)  # Delay difensivo anti-timing e anti-brute force (fuori da lock_login)
                    self.send_error(401, "Unauthorized")
            except Exception as e:
                logging.error(f"Errore login: {e}")
                self.send_error(400, "Bad Request")
                
        elif parsed_path == '/api/admin/save':
            if not self._check_security() or not self._check_token(): return
            
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(body)
                
                # Copy-on-Write: prepariamo la nuova configurazione su una copia isolata
                with lock_config:
                    nuova_config = copy.deepcopy(CONFIG)

                valida_payload_admin_save(payload, config_attuale=nuova_config)
                
                if 'main' in payload:
                    if 'main' not in nuova_config: nuova_config['main'] = {}
                    nuova_config['main'].update(payload['main'])
                
                if 'frontend' in payload:
                    if 'frontend' not in nuova_config: nuova_config['frontend'] = {}
                    if 'quotaCarosello' in payload['frontend']:
                        raw_quota = payload['frontend']['quotaCarosello']
                        if isinstance(raw_quota, bool) or raw_quota is None:
                            payload['frontend']['quotaCarosello'] = 0.30
                        else:
                            try:
                                val_quota = float(raw_quota)
                                if not math.isnan(val_quota) and 0.10 <= val_quota <= 0.50:
                                    payload['frontend']['quotaCarosello'] = round(val_quota, 2)
                                else:
                                    payload['frontend']['quotaCarosello'] = 0.30
                            except (ValueError, TypeError):
                                payload['frontend']['quotaCarosello'] = 0.30
                    nuova_config['frontend'].update(payload['frontend'])
                    
                if 'api_cineca' in payload:
                    nuovo_url = payload['api_cineca'].get('url_base')
                    if nuovo_url is not None and nuovo_url != nuova_config.get('api_cineca', {}).get('url_base') \
                            and payload['api_cineca'].get('password') in (None, '', '********'):
                        self._invia_json(400, {"error": "Per modificare url_base reinserire la password CINECA."})
                        return

                    if 'api_cineca' not in nuova_config: nuova_config['api_cineca'] = {}
                    nuova_pwd = payload['api_cineca'].get('password')
                    if nuova_pwd == '********':
                        payload['api_cineca']['password'] = nuova_config['api_cineca'].get('password', '')
                    for field in ['realm', 'anno_accademico_id', 'contesto_id', 'id_edificio']:
                        if field in payload['api_cineca']:
                            payload['api_cineca'][field] = sanitize_id_str(payload['api_cineca'][field])
                    nuova_config['api_cineca'].update(payload['api_cineca'])
                    
                if 'sicurezza' in payload:
                    if 'sicurezza' not in nuova_config: nuova_config['sicurezza'] = {}
                    if 'admin_ip_autorizzati' in payload['sicurezza']:
                        nuova_config['sicurezza']['admin_ip_autorizzati'] = payload['sicurezza']['admin_ip_autorizzati']
                    if 'admin_attivo' in payload['sicurezza']:
                        nuova_config['sicurezza']['admin_attivo'] = payload['sicurezza']['admin_attivo']
                        
                if 'footer_news' in payload:
                    if 'footer_news' not in nuova_config: nuova_config['footer_news'] = {}
                    nuova_config['footer_news'].update(payload['footer_news'])
                
                if 'https' in payload:
                    if 'https' not in nuova_config: nuova_config['https'] = {}
                    nuova_config['https'].update(payload['https'])
                
                nuova_admin_pwd = payload.get('admin_password', '').strip()
                if nuova_admin_pwd:
                    nuova_config['sicurezza']['password_admin_hash'] = hashlib.sha256(nuova_admin_pwd.encode('utf-8')).hexdigest()
                    
                # Aggiornamento custom su disco per preservare commenti YAML
                salva_config_yaml(FILE_CONFIG, nuova_config)
                
                # Aggiornamento in-place thread-safe della configurazione in RAM (mantiene alias ctx.config)
                with lock_config:
                    CONFIG.clear()
                    CONFIG.update(nuova_config)
                
                news_poll_event.set() # Sveglia il demone per rileggere subito la config delle fonti
                logging.info("💾 Configurazione salvata e applicata con successo da /admin.")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                
            except ValueError as e:
                logging.warning(f"🚫 Errore salvataggio config (payload rifiutato): {e}")
                self._invia_json(400, {"error": str(e)})
            except Exception as e:
                logging.error(f"Errore salvataggio config: {e}")
                self._invia_json(400, {"error": "Bad Request"})
                
        elif parsed_path == '/api/admin/locandine/upload':
            if not self._check_security() or not self._check_token(): return
            if content_length == 0:
                self._invia_json(400, {"error": "Body vuoto"})
                return
            try:
                nome = salva_locandina_da_stream(self.rfile, content_length)
            except ValueError as e:
                self._invia_json(400, {"error": str(e)})
                return
            logging.info(f"🖼️ Locandina caricata: {nome} ({content_length // 1024} KB).")
            self._invia_json(200, {"status": "ok", "filename": nome})

        elif parsed_path == '/api/admin/locandine/ordine':
            if not self._check_security() or not self._check_token(): return
            try:
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode('utf-8'))
            except Exception:
                self._invia_json(400, {"error": "JSON non valido"})
                return
            if not isinstance(payload, dict) or 'ordine' not in payload:
                self._invia_json(400, {"error": "Payload non valido: atteso campo 'ordine'"})
                return
            ordine = payload.get('ordine')
            if not isinstance(ordine, list) or not all(isinstance(n, str) for n in ordine):
                self._invia_json(400, {"error": "Campo 'ordine' deve essere una lista di stringhe"})
                return

            with lock_locandine:
                presenti = elenco_file_locandine()
                insieme = set(presenti)
                nuovo = [n for n in dict.fromkeys(ordine) if n in insieme]
                gia = set(nuovo)
                nuovo += [n for n in presenti if n not in gia]
                scrivi_ordine(nuovo)
            self._invia_json(200, {"status": "ok", "ordine": nuovo})

        elif parsed_path == '/api/admin/locandine/elimina':
            if not self._check_security() or not self._check_token(): return
            try:
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode('utf-8'))
            except Exception:
                self._invia_json(400, {"error": "JSON non valido"})
                return
            if not isinstance(payload, dict):
                self._invia_json(400, {"error": "Payload non valido"})
                return
            nome = payload.get('filename') if 'filename' in payload else payload.get('nome')
            if (not isinstance(nome, str) or not nome or 
                '\x00' in nome or 
                nome in ('.', '..') or 
                os.path.basename(nome) != nome or 
                '/' in nome or '\\' in nome):
                self._invia_json(400, {"error": "Nome file non valido o path traversal rilevato"})
                return

            with lock_locandine:
                if nome not in elenco_file_locandine():
                    self._invia_json(404, {"error": "File non trovato"})
                    return
                try:
                    ctx.elimina_locandina(nome)
                except ValueError as e:
                    self._invia_json(400, {"error": str(e)})
                    return
                except OSError as e:
                    logging.error(f"Errore rimozione file {nome}: {e}")
                    self._invia_json(500, {"error": "Errore durante l'eliminazione del file"})
                    return
            self._invia_json(200, {"status": "ok"})

        elif parsed_path == '/api/admin/restart':
            if not self._check_security() or not self._check_token(): return
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
            logging.info("Riavvio richiesto dall'Admin. Termino il processo (il watchdog Bash lo riavvierà).")
            def restart():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=restart, daemon=True).start()
        else:
            self.send_error(404, "Not Found")

    def serve_file(self, path, mime):
        if os.path.isfile(path):
            self.send_response(200)
            self.send_header('Content-type', mime)
            self.end_headers()
            with open(path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

def avvia_server_https():
    global server_https_attivo
    https_cfg = CONFIG.get('https', {})
    if not https_cfg.get('abilitato', False):
        server_https_attivo = False
        return
    
    cert_file = str(https_cfg.get('file_certificato', 'cert.pem') or 'cert.pem').strip()
    key_file = str(https_cfg.get('file_chiave', 'key.pem') or 'key.pem').strip()
    
    cert_path = cert_file if os.path.isabs(cert_file) else os.path.join(PERCORSO_BASE, cert_file)
    key_path = key_file if os.path.isabs(key_file) else os.path.join(PERCORSO_BASE, key_file)
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        server_https_attivo = False
        logging.warning(f"⚠️ HTTPS abilitato ma file certificato o chiave non trovati ({cert_path}, {key_path}). Server HTTPS non avviato.")
        return

    try:
        porta_https = int(https_cfg.get('porta_https', 8443))
        logging.info(f"Avvio KioskServer HTTPS (SSL) sulla porta {porta_https}")
        
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        httpd_ssl = KioskHTTPServer(('0.0.0.0', porta_https), KioskServer)
        httpd_ssl.is_ssl = True
        httpd_ssl.socket = ssl_ctx.wrap_socket(httpd_ssl.socket, server_side=True)
        server_https_attivo = True
        httpd_ssl.serve_forever()
    except Exception as e:
        server_https_attivo = False
        logging.error(f"Errore critico avvio server HTTPS: {e}")

if __name__ == '__main__':
    pulisci_upload_orfani()
    threading.Thread(target=ciclo_aggiornamento_api, daemon=True).start()
    threading.Thread(target=NewsPollingDaemon, daemon=True).start()
    
    if CONFIG.get('https', {}).get('abilitato', False):
        threading.Thread(target=avvia_server_https, daemon=True).start()
        
    try:
        porta = int(CONFIG.get('main', {}).get('porta_server', 8080))
        logging.info(f"Avvio KioskServer HTTP sulla porta {porta}")
        httpd = KioskHTTPServer(('0.0.0.0', porta), KioskServer)
        httpd.is_ssl = False
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"Errore critico avvio server HTTP: {e}")
