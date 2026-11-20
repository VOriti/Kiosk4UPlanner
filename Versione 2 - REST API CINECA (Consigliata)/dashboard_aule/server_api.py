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
import ipaddress
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
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
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


PERCORSO_BASE = os.path.dirname(os.path.abspath(__file__))
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

LIMITE_EVENTI_CINECA = 500          # tetto 'limit' richiesto a getImpegniCalendario
SOGLIA_ASSENZE_ANNULLAMENTO = 2     # polling consecutivi senza l'evento prima di marcarlo ANNULLATO
AVVISI_DI_STATO = ("ANNULLATO", "SOSPESO")

LIMITE_UPLOAD_LOCANDINA = 10 * 1024 * 1024
LIMITE_POST_JSON = 1 * 1024 * 1024
ESTENSIONI_LOCANDINE = ('.png', '.jpg', '.jpeg', '.webp')

lock_locandine = threading.Lock()

def cartella_locandine():
    return os.path.join(PERCORSO_BASE, 'locandine')

def percorso_ordine():
    return os.path.join(cartella_locandine(), 'ordine.json')

def leggi_ordine():
    try:
        with open(percorso_ordine(), 'r', encoding='utf-8') as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return []
    return [n for n in dati if isinstance(n, str)] if isinstance(dati, list) else []

def scrivi_ordine(nomi):
    cartella = cartella_locandine()
    os.makedirs(cartella, exist_ok=True)
    tmp = percorso_ordine() + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(nomi, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, percorso_ordine())
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

def elenco_locandine_ordinato():
    """Ordine di ordine.json, poi i file non elencati in ordine naturale; voci senza file ignorate."""
    presenti = elenco_file_locandine()
    insieme = set(presenti)
    ordinati = [n for n in dict.fromkeys(leggi_ordine()) if n in insieme]
    gia = set(ordinati)
    return ordinati + [n for n in presenti if n not in gia]

def rileva_formato_immagine(testa):
    """Estensione dedotta dai magic bytes, None se il formato non è ammesso."""
    if testa.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if testa.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if testa[:4] == b'RIFF' and testa[8:12] == b'WEBP':
        return '.webp'
    return None

def chiave_ordinamento_naturale(nome):
    # Tupla omogenea: la vecchia chiave int/str andava in TypeError con nomi misti (1.jpg + p..._ab12.jpg)
    m = re.match(r'^(\d+)', nome)
    return (0, int(m.group(1)), nome.lower()) if m else (1, 0, nome.lower())

def elenco_file_locandine():
    cartella = cartella_locandine()
    if not os.path.isdir(cartella):
        return []
    nomi = [f for f in os.listdir(cartella)
            if not f.startswith('.') and f.lower().endswith(ESTENSIONI_LOCANDINE)
            and os.path.isfile(os.path.join(cartella, f))]
    return sorted(nomi, key=chiave_ordinamento_naturale)

def pulisci_upload_orfani():
    cartella = cartella_locandine()
    if os.path.isdir(cartella):
        for f in os.listdir(cartella):
            if f.startswith('.upload_') and f.endswith('.tmp'):
                try:
                    os.remove(os.path.join(cartella, f))
                except OSError:
                    pass

def salva_locandina_da_stream(rfile, lunghezza):
    """Scrive il body su .tmp a blocchi, valida i magic bytes e rinomina con un nome immutabile."""
    cartella = cartella_locandine()
    os.makedirs(cartella, exist_ok=True)
    tmp = os.path.join(cartella, f'.upload_{secrets.token_hex(8)}.tmp')
    testa, letti = b'', 0
    try:
        with open(tmp, 'wb') as f:
            while letti < lunghezza:
                blocco = rfile.read(min(65536, lunghezza - letti))
                if not blocco:
                    raise ValueError('Upload interrotto prima della fine')
                if len(testa) < 12:
                    testa += blocco[:12 - len(testa)]
                f.write(blocco)
                letti += len(blocco)
            f.flush()
            os.fsync(f.fileno())
        ext = rileva_formato_immagine(testa)
        if not ext:
            raise ValueError('Formato non supportato: ammessi JPEG, PNG, WebP')
        nome = f"p{int(time.time() * 1000)}_{secrets.token_hex(2)}{ext}"
        os.replace(tmp, os.path.join(cartella, nome))
        return nome
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

def get_tz_roma():
    """Restituisce il fuso orario di Roma (Europe/Rome).
    Supporta nativamente zoneinfo su Linux/Raspberry Pi con fallback robusto per Windows/UTC."""
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo("Europe/Rome")
    except Exception:
        pass
    local_tz = datetime.datetime.now().astimezone().tzinfo
    if local_tz and datetime.datetime.now().astimezone().utcoffset() != datetime.timedelta(0):
        return local_tz
    # Fallback calcolato CET (UTC+1) / CEST (UTC+2) per sistemi configurati in UTC puro
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    anno = now_utc.year
    mar_last_sun = max(d for d in range(25, 32) if datetime.date(anno, 3, d).weekday() == 6)
    oct_last_sun = max(d for d in range(25, 32) if datetime.date(anno, 10, d).weekday() == 6)
    dst_start = datetime.datetime(anno, 3, mar_last_sun, 2, 0, tzinfo=datetime.timezone.utc)
    dst_end = datetime.datetime(anno, 10, oct_last_sun, 3, 0, tzinfo=datetime.timezone.utc)
    offset_ore = 2 if dst_start <= now_utc < dst_end else 1
    return datetime.timezone(datetime.timedelta(hours=offset_ore))

def get_giorno_operativo(dt_roma=None):
    """Calcola la data del giorno operativo corrente per l'Ateneo.
    La giornata didattica va dalle 04:00 del mattino alle 03:59 del giorno successivo."""
    tz_roma = get_tz_roma()
    now_roma = dt_roma or datetime.datetime.now(tz_roma)
    if now_roma.hour >= 4:
        return now_roma.date()
    else:
        return now_roma.date() - datetime.timedelta(days=1)

def salva_stato(forza=False):
    """Salva lo stato degli impegni in modo condizionale e atomico.
    Se i dati non sono cambiati, non effettua scritture su disco per tutelare la MicroSD.
    Utilizza un file temporaneo e os.replace per prevenire corruzioni da blackout."""
    global ultimo_stato_json_salvato
    try:
        nuovo_json = json.dumps(storico_impegni, indent=4, sort_keys=True)
        if not forza and nuovo_json == ultimo_stato_json_salvato:
            return  # Nessuna variazione: zero scritture su MicroSD
        
        percorso_def = os.path.join(PERCORSO_BASE, 'stato_impegni.json')
        percorso_tmp = os.path.join(PERCORSO_BASE, 'stato_impegni.json.tmp')
        with open(percorso_tmp, 'w', encoding='utf-8') as f:
            f.write(nuovo_json)
            f.flush()
            os.fsync(f.fileno())
        os.replace(percorso_tmp, percorso_def)
        ultimo_stato_json_salvato = nuovo_json
    except Exception as e:
        logging.error(f"❌ Errore durante il salvataggio atomico dello stato: {e}")

def verifica_e_esegui_reset_04am(dt_roma=None):
    """Verifica ed esegue il reset programmato alle 04:00 AM (o catch-up all'avvio).
    Ritorna True se è stato eseguito un reset dello storico impegni."""
    global storico_impegni, ultimo_reset_data
    tz_roma = get_tz_roma()
    now_roma = dt_roma or datetime.datetime.now(tz_roma)
    giorno_op = get_giorno_operativo(now_roma)
    giorno_op_str = str(giorno_op)

    file_reset = os.path.join(PERCORSO_BASE, 'ultimo_reset.txt')
    if ultimo_reset_data is None:
        if os.path.exists(file_reset):
            try:
                with open(file_reset, 'r', encoding='utf-8') as f:
                    ultimo_reset_data = f.read().strip()
            except Exception:
                ultimo_reset_data = None

    if ultimo_reset_data != giorno_op_str:
        logging.info(f"🔄 Esecuzione reset giornaliero impegni (precedente: {ultimo_reset_data} -> nuovo giorno operativo: {giorno_op_str}).")
        storico_impegni.clear()
        salva_stato()
        ultimo_reset_data = giorno_op_str
        try:
            with open(file_reset, 'w', encoding='utf-8') as f:
                f.write(giorno_op_str)
        except Exception as e:
            logging.warning(f"⚠️ Impossibile salvare ultimo_reset.txt: {e}")
        return True
    return False

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

def carica_stato():
    global storico_impegni, ultimo_reset_data, ultimo_stato_json_salvato
    file_stato = os.path.join(PERCORSO_BASE, 'stato_impegni.json')
    if os.path.exists(file_stato):
        try:
            with open(file_stato, 'r', encoding='utf-8') as f:
                storico_impegni = json.load(f)
                ultimo_stato_json_salvato = json.dumps(storico_impegni, indent=4, sort_keys=True)
        except Exception as e:
            logging.warning(f"⚠️ Impossibile leggere stato_impegni.json (file corrotto o non valido): {e}")
            storico_impegni = {}
            ultimo_stato_json_salvato = None
    
    tz_roma = get_tz_roma()
    now_roma = datetime.datetime.now(tz_roma)
    
    # Catch-up delle 04:00 AM all'avvio (es. accensione portineria alle 07:30):
    if verifica_e_esegui_reset_04am(now_roma):
        logging.info("🧹 Catch-up avvio: storico impegni resettato per la nuova giornata operativa.")
    else:
        # Se siamo nella stessa giornata operativa, rimuoviamo solo eventuali eventi scaduti
        dt_inizio_giorno = datetime.datetime.combine(get_giorno_operativo(now_roma), datetime.time(0, 0, 0), tzinfo=tz_roma)
        mezzanotte_ts = dt_inizio_giorno.timestamp()
        storico_impegni = {k: v for k, v in storico_impegni.items() if v.get('timestamp_fine', 0) > mezzanotte_ts}

carica_stato()

def sanitize_id_str(val):
    """Sanitizza gli identificativi CINECA rimuovendo spazi e apici accidentali ed evitando 'None'."""
    if val is None:
        return ''
    import re
    return re.sub(r"^[\s\'\"]+|[\s\'\"]+$", '', str(val))

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
    logging.info("Richiesta di un nuovo Token a CINECA (Admin) in corso...")
    
    api_cineca = CONFIG.get('api_cineca', {})
    url_base = str(api_cineca.get('url_base') or 'https://cineca.prod.up.cineca.it/api').strip().rstrip('/')
    url_login = f"{url_base}/Utenti/login"
    
    realm = sanitize_id_str(api_cineca.get('realm'))
    payload = {
        "username": api_cineca.get('username', ''), 
        "password": api_cineca.get('password', ''), 
        "realm": realm,
        "clientId": realm
    }
    try:
        risposta = requests.post(url_login, json=payload, timeout=10)   
        if risposta.status_code == 200:
            dati = risposta.json()
            token_cineca = dati.get("id")
            logging.info("✅ Login effettuato con successo. Nuovo token acquisito.")
            return True
        else:
            logging.error(f"❌ Errore di Login. Codice: {risposta.status_code}. Risposta: {risposta.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Errore di rete durante il login: {e}")
        return False

def estrai_e_formatta_dati(impegni_grezzi):
    global storico_impegni, data_storico
    tz_roma = get_tz_roma()
    ora_attuale = datetime.datetime.now(tz_roma)
    oggi_str = str(get_giorno_operativo(ora_attuale))
    
    if oggi_str != data_storico:
        data_storico = oggi_str
        
    nuovi_estratti = {}
    id_esclusi = set()      # presenti in CINECA ma esclusi dalla configurazione corrente (edificio, stato B, C nascosti)
    id_illeggibili = set()  # presenti in CINECA ma non interpretabili: non vanno mai trattati come annullati
    for item in impegni_grezzi:
        id_imp = (item.get('id') or item.get('_id')) if isinstance(item, dict) else None
        if not id_imp: continue
        try:
            aule = item.get('aule', [])
            edifici_impegno = [sanitize_id_str(a.get('edificio', {}).get('codice')) for a in aule if isinstance(a, dict) and a.get('edificio')]
            
            id_edificio = sanitize_id_str(CONFIG.get('api_cineca', {}).get('id_edificio'))
            if id_edificio != "":
                edifici_norm = set(edifici_impegno) | {c.lstrip('0') or '0' for c in edifici_impegno}
                id_norm = id_edificio.lstrip('0') or '0'
                if id_edificio not in edifici_norm and id_norm not in edifici_norm:
                    id_esclusi.add(id_imp)
                    continue

            stato = item.get('stato', 'P')
            if isinstance(stato, dict):
                stato = stato.get('codice') or stato.get('id') or 'P'
            stato = str(stato).upper().strip()

            if stato == 'B':
                id_esclusi.add(id_imp)
                continue
                
            mostra_confermati = CONFIG.get('frontend', {}).get('mostra_confermati', True)
            if stato == 'C' and not mostra_confermati:
                id_esclusi.add(id_imp)
                continue

            is_cancellato = (stato == 'A')
            avviso_stato = ""
            if stato == 'A': avviso_stato = "ANNULLATO"
            elif stato == 'S': avviso_stato = "SOSPESO"

            str_inizio = item.get('dataInizio', '').replace('Z', '+00:00')
            str_fine = item.get('dataFine', '').replace('Z', '+00:00')
            dt_inizio = datetime.datetime.fromisoformat(str_inizio)
            dt_fine = datetime.datetime.fromisoformat(str_fine)
            
            evento = item.get('evento', {})
            
            is_indisponibilita = (
                item.get('indisponibilita', False) or 
                item.get('indisponibilitaTotale', False) or 
                item.get('indisponibilitaTotaleAule', False) or 
                item.get('tipoImpegno') == 'INDISPONIBILITA'
            )
            
            testo_estratto = (item.get('nome') or item.get('causaleIndisponibilita') or item.get('note') or evento.get('nome') or item.get('motivo') or item.get('descrizione') or evento.get('dettaglioDidattico', {}).get('nome') or "Attività programmata")
            
            if is_indisponibilita:
                titolo_raw = f"INDISPONIBILITÀ: {testo_estratto}"
            else:
                titolo_raw = testo_estratto

            nuovi_estratti[id_imp] = {
                "id": id_imp,
                "orario": f"{dt_inizio.astimezone(tz_roma).strftime('%H:%M')} - {dt_fine.astimezone(tz_roma).strftime('%H:%M')}",
                "titolo": titolo_raw.strip(),
                "docente": f"{item.get('docenti', [{}])[0].get('cognome', '')} {item.get('docenti', [{}])[0].get('nome', '')}".strip() if item.get('docenti') else "Dipartimento",
                "aula": (aule[0].get('descrizione') or 'Da definire').strip() if aule else "Da definire",
                "inCorso": (dt_inizio <= ora_attuale <= dt_fine),
                "timestamp_inizio": dt_inizio.timestamp(),
                "timestamp_fine": dt_fine.timestamp(),
                "cancellato": is_cancellato,
                "avviso": avviso_stato,
                "stato_cineca": stato,
                "assenze": 0
            }
        except Exception as e:
            id_illeggibili.add(id_imp)
            logging.warning(f"⚠️ Impegno CINECA {id_imp} non interpretabile ({e}): stato precedente preservato.")

    # Un evento escluso dai filtri NON è annullato: esce semplicemente dallo storico
    for id_escluso in id_esclusi:
        storico_impegni.pop(id_escluso, None)

    for id_nuovo, imp_nuovo in nuovi_estratti.items():
        if id_nuovo not in storico_impegni:
            storico_impegni[id_nuovo] = imp_nuovo
        else:
            imp_storico = storico_impegni[id_nuovo]

            # Auto-healing: l'evento è di nuovo regolare in CINECA, si rimuove l'avviso di stato ereditato
            if not imp_nuovo['avviso'] and imp_storico.get('avviso') in AVVISI_DI_STATO:
                imp_storico['avviso'] = ""
                imp_storico['cancellato'] = False

            cambiata_aula = imp_storico['aula'] != imp_nuovo['aula']
            cambiato_orario = imp_storico['orario'] != imp_nuovo['orario']
            
            if (cambiata_aula or cambiato_orario) and not imp_storico.get('avviso', '').startswith("Spostato"):
                vecchia_aula = imp_storico['aula']
                vecchio_orario = imp_storico['orario']
                imp_storico['avviso'] = f"Spostato (da {vecchia_aula} ore {vecchio_orario})"
            
            if imp_nuovo['avviso']:
                imp_storico['avviso'] = imp_nuovo['avviso']
                imp_storico['cancellato'] = imp_nuovo['cancellato']
            else:
                imp_nuovo['avviso'] = imp_storico.get('avviso', "")
            
            imp_storico.update(imp_nuovo)

    # Protezione anti-falso annullamento:
    # Se la risposta da CINECA e vuota ma avevamo gia impegni validi nello storico,
    # non marchiamo gli eventi come annullati per evitare falsi allarmi sul totem.
    global ultimo_aggiornamento_preservato
    if len(impegni_grezzi) == 0 and len(storico_impegni) > 0:
        logging.warning("⚠️ Rilevato payload CINECA vuoto a fronte di impegni validi in memoria. Preservo lo stato per evitare falsi annullamenti.")
        ultimo_aggiornamento_preservato = True
    else:
        ultimo_aggiornamento_preservato = False
        # Un evento sparito diventa ANNULLATO solo dopo SOGLIA_ASSENZE_ANNULLAMENTO polling consecutivi
        for id_storico, imp_storico in storico_impegni.items():
            if id_storico in nuovi_estratti or id_storico in id_illeggibili:
                continue
            if imp_storico['timestamp_fine'] > ora_attuale.timestamp() and not imp_storico.get('cancellato'):
                imp_storico['assenze'] = imp_storico.get('assenze', 0) + 1
                if imp_storico['assenze'] >= SOGLIA_ASSENZE_ANNULLAMENTO:
                    imp_storico["cancellato"] = True
                    imp_storico["avviso"] = "ANNULLATO"
                    logging.info(f"🚫 Impegno {id_storico} assente da CINECA per {imp_storico['assenze']} polling consecutivi: marcato ANNULLATO.")

    dt_inizio_giorno = datetime.datetime.combine(get_giorno_operativo(ora_attuale), datetime.time(0, 0, 0), tzinfo=tz_roma)
    mezzanotte_oggi = dt_inizio_giorno.timestamp()
    chiavi_scadute = [k for k, v in storico_impegni.items() if v.get('timestamp_fine', 0) <= mezzanotte_oggi]
    for k in chiavi_scadute:
        del storico_impegni[k]

    for imp in storico_impegni.values():
         imp['inCorso'] = (imp['timestamp_inizio'] <= ora_attuale.timestamp() <= imp['timestamp_fine'])

    salva_stato()

    dati_puliti = [imp for imp in storico_impegni.values() if imp['timestamp_fine'] > ora_attuale.timestamp() or imp['inCorso']]
    dati_puliti.sort(key=lambda x: x['timestamp_inizio'])
    return dati_puliti

def verifica_sentinella_limite(dati_grezzi):
    """Segnala nel log una risposta CINECA arrivata al tetto 'limit' (possibile troncatura)."""
    if isinstance(dati_grezzi, list) and len(dati_grezzi) >= LIMITE_EVENTI_CINECA:
        logging.warning(f"⚠️ SENTINELLA LIMITE CINECA: ricevuti {len(dati_grezzi)} impegni (limite {LIMITE_EVENTI_CINECA}). Possibile troncatura: valorizzare anno_accademico_id e contesto_id.")
        return True
    return False

def intervallo_aggiornamento_sec():
    try:
        intervallo = int(CONFIG.get('api_cineca', {}).get('intervallo_aggiornamento_sec') or 300)
        return intervallo if intervallo > 0 else 300
    except (ValueError, TypeError):
        return 300

def elabora_risposta_cineca(dati_grezzi):
    global memoria_dati, ultimo_sync_cineca_ok
    verifica_sentinella_limite(dati_grezzi)
    with lock_memoria:
        memoria_dati = estrai_e_formatta_dati(dati_grezzi)
    ultimo_sync_cineca_ok = time.time()
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
                    time.sleep(120)
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
                time.sleep(2)
                continue
            elif risposta.status_code == 200:
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

DIAGNOSTICA_NEWS = {}   # url -> {"stato", "articoli", "ora"}; sostituito per intero a ogni giro

def classifica_errore_fonte(exc):
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

TIMEOUT_FONTE_NEWS_SEC = 5

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile(r'<.*?>', re.DOTALL)
    cleantext = re.sub(cleanr, '', str(raw_html))
    return cleantext.strip()

def parse_data_notizia(raw):
    if not raw: return ''
    raw = raw.strip()
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(raw)
        if dt: return dt.strftime('%d/%m/%Y')
    except Exception:
        pass
    m1 = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', raw)
    if m1:
        d, m, y = m1.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
    mesi = {
        'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
        'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12,
        'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
        'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
    }
    m2 = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})', raw)
    if m2:
        d, mese_str, y = m2.groups()
        mese_num = mesi.get(mese_str.lower()[:3]) or mesi.get(mese_str.lower())
        if mese_num:
            return f"{int(d):02d}/{mese_num:02d}/{y}"
    m3 = re.search(r'(\d{4})-(\d{2})-(\d{2})', raw)
    if m3:
        y, m, d = m3.groups()
        return f"{int(d):02d}/{int(m):02d}/{y}"
    return raw

def normalizza_peso(valore):
    try:
        return min(5, max(1, int(valore)))
    except (TypeError, ValueError):
        return 1

def scarica_fonte(fonte):
    url = fonte.get('url', '').strip()
    tipo = fonte.get('tipo', '').lower()
    nome = fonte.get('nome', 'Fonte')
    visibile = fonte.get('visibile_di_default', True)

    if not url:
        return []

    notizie_di_questa_fonte = []
    res = requests.get(url, timeout=TIMEOUT_FONTE_NEWS_SEC)
    res.raise_for_status()

    if tipo == 'rest':
        dati = res.json()
        for item in dati:
            title = item.get('title', {}).get('rendered', '')
            link = item.get('link', '')
            data = parse_data_notizia(item.get('date', ''))
            titolo_pulito = clean_html(title)
            if titolo_pulito:
                notizie_di_questa_fonte.append({"fonte": nome, "titolo": titolo_pulito, "link": link, "data": data, "visibile": visibile})
    elif tipo == 'rss':
        root = ET.fromstring(res.content)
        items = root.findall('./channel/item')
        if not items:
            # Supporto fallback per formati Atom (Drupal Views / feed alternativi)
            items = root.findall('.//{http://www.w3.org/2005/Atom}entry') or root.findall('.//entry')

        for item in items:
            title = item.find('{http://www.w3.org/2005/Atom}title') if item.find('{http://www.w3.org/2005/Atom}title') is not None else item.find('title')
            link_elem = item.find('{http://www.w3.org/2005/Atom}link') if item.find('{http://www.w3.org/2005/Atom}link') is not None else item.find('link')
            date_elem = None
            for tag_candidate in ['{http://www.w3.org/2005/Atom}updated', '{http://www.w3.org/2005/Atom}published', 'pubDate', '{http://purl.org/dc/elements/1.1/}date', 'date']:
                found_el = item.find(tag_candidate)
                if found_el is not None:
                    date_elem = found_el
                    break

            link = ''
            if link_elem is not None:
                link = link_elem.get('href', '') or (link_elem.text.strip() if link_elem.text else '')
            raw_data = date_elem.text.strip() if date_elem is not None and date_elem.text else ''
            data = parse_data_notizia(raw_data)

            titolo_raw = "".join(title.itertext()).strip() if title is not None else ""
            # Compatibilità avanzata Drupal: se il link non è in <link>, estrailo da tag <a> o CDATA del titolo
            if not link and title is not None:
                a_elem = title.find('.//a')
                if a_elem is not None and a_elem.get('href'):
                    link = a_elem.get('href')
                elif 'href=' in str(titolo_raw):
                    m_href = re.search(r'href="([^"]+)"', str(titolo_raw)) or re.search(r"href='([^']+)'", str(titolo_raw))
                    if m_href:
                        link = m_href.group(1).strip()

            titolo_pulito = clean_html(titolo_raw)
            if titolo_pulito:
                notizie_di_questa_fonte.append({"fonte": nome, "titolo": titolo_pulito, "link": link.strip(), "data": data, "visibile": visibile})
    return notizie_di_questa_fonte

def aggiorna_news_una_volta():
    global memoria_news, DIAGNOSTICA_NEWS
    footer_config = CONFIG.get('footer_news', {})
    fonti = footer_config.get('fonti', [])
    notizie_per_fonte = []
    diagnostica = {}
    tz_roma = get_tz_roma()

    for fonte in fonti:
        url = fonte.get('url', '').strip()
        nome = fonte.get('nome', 'Fonte')
        abilitata = fonte.get('abilitata', True)
        peso = normalizza_peso(fonte.get('peso', 1))

        if not url:
            continue

        if not abilitata:
            diagnostica[url] = {"stato": "DISABILITATA", "articoli": 0, "ora": ""}
            continue

        try:
            notizie_di_questa_fonte = scarica_fonte(fonte)
            ora_roma = datetime.datetime.now(tz_roma).strftime('%H:%M')
            diagnostica[url] = {"stato": "OK", "articoli": len(notizie_di_questa_fonte), "ora": ora_roma}
            if notizie_di_questa_fonte:
                notizie_per_fonte.append({'notizie': notizie_di_questa_fonte, 'peso': peso})
        except Exception as e:
            ora_roma = datetime.datetime.now(tz_roma).strftime('%H:%M')
            diagnostica[url] = {"stato": classifica_errore_fonte(e), "articoli": 0, "ora": ora_roma}
            logging.warning(f"⚠️ Errore recupero news da {nome} ({url}): {e}")

    DIAGNOSTICA_NEWS = diagnostica

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

class KioskServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass 

    def end_headers(self):
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
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
            self.serve_file(os.path.join(PERCORSO_BASE, 'remoto.html'), 'text/html')
        elif parsed_path == '/remoto.html':
            qs = ('?' + self.path.split('?', 1)[1]) if '?' in self.path else ''
            self.send_response(301)
            self.send_header('Location', '/' + qs)
            self.end_headers()
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
            with lock_memoria: self.wfile.write(json.dumps(memoria_dati).encode('utf-8'))
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
                self.serve_file(os.path.join(PERCORSO_BASE, 'admin.html'), 'text/html')
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
                
                hash_salvato = CONFIG.get('sicurezza', {}).get('password_admin_hash', '')
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
            now_ts = time.time()
            
            with lock_login:
                tentativo = LOGIN_ATTEMPTS.get(client_ip, {'count': 0, 'locked_until': 0})
                if tentativo.get('locked_until', 0) > now_ts:
                    secondi_attesa = int(tentativo['locked_until'] - now_ts)
                    self.send_response(429)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": f"Troppi tentativi falliti. Riprova tra {secondi_attesa} secondi.",
                        "secondi_attesa": secondi_attesa
                    }).encode('utf-8'))
                    return

            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                pwd = data.get('password', '')
                pwd_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
                
                hash_salvato = CONFIG.get('sicurezza', {}).get('password_admin_hash', '')
                
                if pwd_hash == hash_salvato:
                    with lock_login:
                        if client_ip in LOGIN_ATTEMPTS:
                            del LOGIN_ATTEMPTS[client_ip]
                    token = secrets.token_hex(16)
                    SESSIONS[token] = time.time() + 3600
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"token": token}).encode('utf-8'))
                else:
                    time.sleep(1)  # Delay difensivo anti-timing e anti-brute force
                    with lock_login:
                        tentativo = LOGIN_ATTEMPTS.get(client_ip, {'count': 0, 'locked_until': 0})
                        tentativo['count'] = tentativo.get('count', 0) + 1
                        if tentativo['count'] >= 5:
                            tentativo['locked_until'] = now_ts + 600  # Blocco per 10 minuti
                            logging.warning(f"🚨 Troppi tentativi di login errati dall'IP {client_ip}. IP bloccato per 10 minuti.")
                        LOGIN_ATTEMPTS[client_ip] = tentativo
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
                
                # Riassegnazione atomica thread-safe della configurazione in RAM
                with lock_config:
                    CONFIG = nuova_config
                
                news_poll_event.set() # Sveglia il demone per rileggere subito la config delle fonti
                logging.info("💾 Configurazione salvata e applicata con successo da /admin.")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                
            except Exception as e:
                logging.error(f"Errore salvataggio config: {e}")
                self.send_error(400, "Bad Request")
                
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
                presenti = elenco_file_locandine()
                if nome not in presenti:
                    self._invia_json(404, {"error": "File non trovato"})
                    return
                percorso = os.path.join(cartella_locandine(), nome)
                try:
                    os.remove(percorso)
                except OSError as e:
                    logging.error(f"Errore rimozione file {nome}: {e}")
                    self._invia_json(500, {"error": "Errore durante l'eliminazione del file"})
                    return
                scrivi_ordine(elenco_locandine_ordinato())
                logging.info(f"🗑️ Locandina eliminata: {nome}")
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
            if mime in ['text/html', 'text/javascript']:
                with open(path, 'r', encoding='utf-8') as f: self.wfile.write(f.read().encode('utf-8'))
            else:
                with open(path, 'rb') as f: self.wfile.write(f.read())
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
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        httpd_ssl = KioskHTTPServer(('0.0.0.0', porta_https), KioskServer)
        httpd_ssl.is_ssl = True
        httpd_ssl.socket = ctx.wrap_socket(httpd_ssl.socket, server_side=True)
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
