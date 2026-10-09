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
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver

PERCORSO_BASE = os.path.dirname(os.path.abspath(__file__))
FILE_CONFIG = os.path.join(PERCORSO_BASE, 'config.yaml')

CONFIG = {}
SESSIONS = {}
memoria_dati = []
lock_memoria = threading.Lock()
token_cineca = None
storico_impegni = {}
data_storico = None
memoria_news = []
news_poll_event = threading.Event()

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
  urlLogo: '/logo.png'
  mostraStatoPC: true
  messaggioNessunaLezione: 'Nessun impegno attivo programmato per la giornata.'
  messaggioErroreRete: 'Connessione persa col Server API. Tentativo di riconnessione...'
  pausaTraCaroselli: 180000
  esposizioneLocandina: 10000
  intervalloAggiornamento: 5000
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

file_log = os.path.join(PERCORSO_BASE, CONFIG.get('main', {}).get('file_log', 'kiosk.log'))
logging.basicConfig(
    filename=file_log,
    level=logging.INFO,
    format='%(asctime)s - [API SERVER] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

def carica_stato():
    global storico_impegni
    if os.path.exists(os.path.join(PERCORSO_BASE, 'stato_impegni.json')):
        with open(os.path.join(PERCORSO_BASE, 'stato_impegni.json'), 'r', encoding='utf-8') as f:
            storico_impegni = json.load(f)
    
    ora_attuale = datetime.datetime.now(datetime.timezone.utc)
    mezzanotte_oggi = ora_attuale.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    storico_impegni = {k: v for k, v in storico_impegni.items() if v['timestamp_fine'] > mezzanotte_oggi}

carica_stato()

def salva_stato():
    with open(os.path.join(PERCORSO_BASE, 'stato_impegni.json'), 'w', encoding='utf-8') as f:
        json.dump(storico_impegni, f, indent=4)

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
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

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
    ora_attuale = datetime.datetime.now(datetime.timezone.utc)
    oggi_str = ora_attuale.strftime("%Y-%m-%d")
    
    if oggi_str != data_storico:
        data_storico = oggi_str
        
    nuovi_estratti = {}
    for item in impegni_grezzi:
        try:
            id_imp = item.get('id') or item.get('_id')
            if not id_imp: continue
            
            aule = item.get('aule', [])
            edifici_impegno = [sanitize_id_str(a.get('edificio', {}).get('codice')) for a in aule if isinstance(a, dict) and a.get('edificio')]
            
            id_edificio = sanitize_id_str(CONFIG.get('api_cineca', {}).get('id_edificio'))
            if id_edificio != "":
                edifici_norm = set(edifici_impegno) | {c.lstrip('0') or '0' for c in edifici_impegno}
                id_norm = id_edificio.lstrip('0') or '0'
                if id_edificio not in edifici_norm and id_norm not in edifici_norm:
                    continue

            stato = item.get('stato', 'P')
            if isinstance(stato, dict):
                stato = stato.get('codice') or stato.get('id') or 'P'
            stato = str(stato).upper().strip()

            if stato == 'B': continue
                
            mostra_confermati = CONFIG.get('frontend', {}).get('mostra_confermati', True)
            if stato == 'C' and not mostra_confermati: continue

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
                "orario": f"{dt_inizio.astimezone().strftime('%H:%M')} - {dt_fine.astimezone().strftime('%H:%M')}",
                "titolo": titolo_raw.strip(),
                "docente": f"{item.get('docenti', [{}])[0].get('cognome', '')} {item.get('docenti', [{}])[0].get('nome', '')}".strip() if item.get('docenti') else "Dipartimento",
                "aula": aule[0].get('descrizione', 'Da definire').strip() if aule else "Da definire",
                "inCorso": (dt_inizio <= ora_attuale <= dt_fine),
                "timestamp_inizio": dt_inizio.timestamp(),
                "timestamp_fine": dt_fine.timestamp(),
                "cancellato": is_cancellato,
                "avviso": avviso_stato,
                "stato_cineca": stato
            }
        except Exception:
            continue

    for id_nuovo, imp_nuovo in nuovi_estratti.items():
        if id_nuovo not in storico_impegni:
            storico_impegni[id_nuovo] = imp_nuovo
        else:
            imp_storico = storico_impegni[id_nuovo]
            
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

    for id_storico, imp_storico in storico_impegni.items():
        if id_storico not in nuovi_estratti and imp_storico['timestamp_fine'] > ora_attuale.timestamp():
            imp_storico["cancellato"] = True
            imp_storico["avviso"] = "ANNULLATO"

    mezzanotte_oggi = ora_attuale.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    chiavi_scadute = [k for k, v in storico_impegni.items() if v['timestamp_fine'] <= mezzanotte_oggi]
    for k in chiavi_scadute:
        del storico_impegni[k]

    for imp in storico_impegni.values():
         imp['inCorso'] = (imp['timestamp_inizio'] <= ora_attuale.timestamp() <= imp['timestamp_fine'])

    salva_stato()

    dati_puliti = [imp for imp in storico_impegni.values() if imp['timestamp_fine'] > ora_attuale.timestamp() or imp['inCorso']]
    dati_puliti.sort(key=lambda x: x['timestamp_inizio'])
    return dati_puliti

def ciclo_aggiornamento_api():
    global token_cineca, memoria_dati
    logging.info("🚀 Avviato demone API CINECA (Modalità Admin Autenticata).")
    
    while True:
        try:
            api_cineca = CONFIG.get('api_cineca', {})
            realm = sanitize_id_str(api_cineca.get('realm'))
            url_base = str(api_cineca.get('url_base') or 'https://cineca.prod.up.cineca.it/api').strip().rstrip('/')
            url_impegni = f"{url_base}/Impegni/getImpegniCalendario"
            try:
                intervallo = int(api_cineca.get('intervallo_aggiornamento_sec') or 300)
            except (ValueError, TypeError):
                intervallo = 300
            
            if not token_cineca:
                if not effettua_login():
                    time.sleep(120)
                    continue
            
            headers = { 
                "Authorization": token_cineca,
                "Content-Type": "application/json",
                "X-Realm": realm 
            }            
            
            oggi = datetime.datetime.now(datetime.timezone.utc)
            inizio_giornata = oggi.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            fine_giornata = oggi.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            payload = {
                "limit": 500,
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

            
            logging.info(f"DEBUG: Richiesta impegni a {url_impegni}")
            risposta = requests.post(url_impegni, json=payload, headers=headers, timeout=15)
            
            if risposta.status_code == 401:
                logging.error("❌ Token scaduto o non valido (401). Forzo il rinnovo.")
                token_cineca = None
                time.sleep(2)
                continue
            elif risposta.status_code == 200:
                dati_grezzi = risposta.json()
                if CONFIG.get('main', {}).get('debug_mode', False):
                    logging.info(f"🕵️ DEBUG: Ricevuti {len(dati_grezzi)} impegni grezzi.")
                with lock_memoria:
                    memoria_dati = estrai_e_formatta_dati(dati_grezzi)
                logging.info(f"✅ Dati ricevuti! Trovati {len(memoria_dati)} impegni.")
            else:
                logging.error(f"❌ Errore HTTP {risposta.status_code}: {risposta.text[:100]}")
                
        except Exception as e:
            logging.error(f"❌ Errore critico nel ciclo API: {e}")
        
        # Intervallo aggiornato con fallback sicuro per evitare che il thread si interrompa
        try:
            intervallo = int(CONFIG.get('api_cineca', {}).get('intervallo_aggiornamento_sec') or 300)
            if intervallo <= 0:
                intervallo = 300
        except (ValueError, TypeError):
            intervallo = 300
        time.sleep(intervallo)

def NewsPollingDaemon():
    global memoria_news
    logging.info("🚀 Avviato demone News (Footer).")
    import xml.etree.ElementTree as ET
    import re
    
    def clean_html(raw_html):
        if not raw_html: return ""
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', str(raw_html))
        return cleantext.strip()
        
    while True:
        try:
            footer_config = CONFIG.get('footer_news', {})
            if not footer_config.get('abilitato', False):
                news_poll_event.wait(3600)
                news_poll_event.clear()
                continue
                
            notizie_per_fonte = []
            fonti = footer_config.get('fonti', [])
            
            for fonte in fonti:
                url = fonte.get('url', '').strip()
                tipo = fonte.get('tipo', '').lower()
                nome = fonte.get('nome', 'Fonte')
                abilitata = fonte.get('abilitata', True)
                visibile = fonte.get('visibile_di_default', True)
                peso = fonte.get('peso', 1)
                
                if not url or not abilitata:
                    continue
                    
                notizie_di_questa_fonte = []
                try:
                    res = requests.get(url, timeout=10)
                    res.raise_for_status()
                    
                    if tipo == 'rest':
                        dati = res.json()
                        for item in dati:
                            title = item.get('title', {}).get('rendered', '')
                            link = item.get('link', '')
                            data = item.get('date', '')
                            if title:
                                notizie_di_questa_fonte.append({"fonte": nome, "titolo": clean_html(title), "link": link, "data": data, "visibile": visibile})
                    elif tipo == 'rss':
                        root = ET.fromstring(res.text)
                        for item in root.findall('./channel/item'):
                            title = item.find('title')
                            link_elem = item.find('link')
                            date_elem = item.find('pubDate')
                            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ''
                            data = date_elem.text.strip() if date_elem is not None and date_elem.text else ''
                            if title is not None and title.text:
                                notizie_di_questa_fonte.append({"fonte": nome, "titolo": clean_html(title.text), "link": link, "data": data, "visibile": visibile})
                except Exception as e:
                    logging.error(f"⚠️ Errore recupero news da {nome} ({url}): {e}")
                
                if notizie_di_questa_fonte:
                    # Aggiungiamo un dizionario che contiene sia la lista di notizie sia il peso
                    notizie_per_fonte.append({'notizie': notizie_di_questa_fonte, 'peso': peso})
            
            notizie_estratte = []
            if notizie_per_fonte:
                max_len = max(len(f['notizie']) for f in notizie_per_fonte)
                # Calcoliamo il numero di round massimi necessari (arrotondato per eccesso diviso il peso)
                # Più semplicemente, iteriamo ciclicamente fino ad esaurire la fonte più lunga
                
                ancora_notizie = True
                indici = [0] * len(notizie_per_fonte)
                
                while ancora_notizie:
                    ancora_notizie = False
                    for i, f in enumerate(notizie_per_fonte):
                        peso = f['peso']
                        notizie = f['notizie']
                        idx = indici[i]
                        
                        # Aggiungi 'peso' notizie di questa fonte
                        for k in range(peso):
                            if idx < len(notizie):
                                notizie_estratte.append(notizie[idx])
                                idx += 1
                                indici[i] = idx
                                ancora_notizie = True
                            
            memoria_news = notizie_estratte
        except Exception as e:
            logging.error(f"❌ Errore critico demone News: {e}")
            
        news_poll_event.wait(3600)
        news_poll_event.clear()

class KioskServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass 
    
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
        if not token or token not in SESSIONS:
            self.send_error(401, "Unauthorized")
            return False
        if SESSIONS[token] < time.time():
            del SESSIONS[token]
            self.send_error(401, "Unauthorized")
            return False
        return True
        
    def do_GET(self):
        parsed_path = self.path.split('?')[0]
        if parsed_path == '/':
            self.serve_file(os.path.join(PERCORSO_BASE, 'remoto.html'), 'text/html')
        elif parsed_path == '/remoto.html':
            self.send_response(301)
            self.send_header('Location', '/')
            self.end_headers()
        elif parsed_path == '/config_pubblica':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            frontend_config = CONFIG.get('frontend', {})
            footer_news_config = CONFIG.get('footer_news', {})
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
        elif parsed_path == '/logo.png': 
            self.serve_file(os.path.join(PERCORSO_BASE, 'logo.png'), 'image/png')
        elif parsed_path.startswith('/locandine/'): 
            self.serve_file(os.path.join(PERCORSO_BASE, 'locandine', os.path.basename(parsed_path)), 'image/jpeg')
        elif parsed_path == '/lista_locandine.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                cartella_locandine = os.path.join(PERCORSO_BASE, 'locandine')
                if os.path.exists(cartella_locandine):
                    immagini = [f for f in os.listdir(cartella_locandine) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                    self.wfile.write(json.dumps(immagini).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps([]).encode('utf-8'))
            except Exception as e:
                logging.error(f"Errore lettura locandine: {e}")
                self.wfile.write(json.dumps([]).encode('utf-8'))
        elif parsed_path == '/admin':
            if self._check_security():
                self.serve_file(os.path.join(PERCORSO_BASE, 'admin.html'), 'text/html')
        elif parsed_path == '/api/admin/config_full':
            if self._check_security() and self._check_token():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                safe_config = json.loads(json.dumps(CONFIG))
                if 'api_cineca' in safe_config and 'password' in safe_config['api_cineca']:
                    safe_config['api_cineca']['password'] = '********'
                
                hash_salvato = CONFIG.get('sicurezza', {}).get('password_admin_hash', '')
                if hash_salvato in ['8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', '737a5c64f7f67b7f86e6b6b96698eb5d24b85ba933dd2710b867e16b6b6b9669', 'a45090e56b7639cae365ee553d321fe8ef76300adcab875a064bb3f0abbc08d0']:
                    safe_config['avviso_sicurezza'] = True
                else:
                    safe_config['avviso_sicurezza'] = False
                    
                self.wfile.write(json.dumps(safe_config).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_path = self.path.split('?')[0]
        if parsed_path == '/api/admin/login':
            if not self._check_security(): return
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                pwd = data.get('password', '')
                pwd_hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
                
                hash_salvato = CONFIG.get('sicurezza', {}).get('password_admin_hash', '')
                
                if pwd_hash == hash_salvato:
                    token = secrets.token_hex(16)
                    SESSIONS[token] = time.time() + 3600
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"token": token}).encode('utf-8'))
                else:
                    self.send_error(401, "Unauthorized")
            except Exception as e:
                logging.error(f"Errore login: {e}")
                self.send_error(400, "Bad Request")
                
        elif parsed_path == '/api/admin/save':
            if not self._check_security() or not self._check_token(): return
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(body)
                
                if 'main' in payload:
                    if 'main' not in CONFIG: CONFIG['main'] = {}
                    CONFIG['main'].update(payload['main'])
                
                if 'frontend' in payload:
                    if 'frontend' not in CONFIG: CONFIG['frontend'] = {}
                    CONFIG['frontend'].update(payload['frontend'])
                    
                if 'api_cineca' in payload:
                    if 'api_cineca' not in CONFIG: CONFIG['api_cineca'] = {}
                    nuova_pwd = payload['api_cineca'].get('password')
                    if nuova_pwd == '********':
                        payload['api_cineca']['password'] = CONFIG['api_cineca'].get('password', '')
                    for field in ['realm', 'anno_accademico_id', 'contesto_id', 'id_edificio']:
                        if field in payload['api_cineca']:
                            payload['api_cineca'][field] = sanitize_id_str(payload['api_cineca'][field])
                    CONFIG['api_cineca'].update(payload['api_cineca'])
                    
                if 'sicurezza' in payload:
                    if 'sicurezza' not in CONFIG: CONFIG['sicurezza'] = {}
                    if 'admin_ip_autorizzati' in payload['sicurezza']:
                        CONFIG['sicurezza']['admin_ip_autorizzati'] = payload['sicurezza']['admin_ip_autorizzati']
                    if 'admin_attivo' in payload['sicurezza']:
                        CONFIG['sicurezza']['admin_attivo'] = payload['sicurezza']['admin_attivo']
                        
                if 'footer_news' in payload:
                    if 'footer_news' not in CONFIG: CONFIG['footer_news'] = {}
                    CONFIG['footer_news'].update(payload['footer_news'])
                
                nuova_admin_pwd = payload.get('admin_password', '').strip()
                if nuova_admin_pwd:
                    CONFIG['sicurezza']['password_admin_hash'] = hashlib.sha256(nuova_admin_pwd.encode('utf-8')).hexdigest()
                    
                # Aggiornamento custom per preservare i commenti
                salva_config_yaml(FILE_CONFIG, CONFIG)
                
                load_config() # Ricarica per sicurezza
                news_poll_event.set() # Sveglia il demone per rileggere subito la config delle fonti
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                
            except Exception as e:
                logging.error(f"Errore salvataggio config: {e}")
                self.send_error(400, "Bad Request")
                
        elif parsed_path == '/api/admin/restart':
            if not self._check_security() or not self._check_token(): return
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
            logging.info("Riavvio richiesto dall'Admin. Termino il processo (il watchdog Bash lo riavvierà).")
            import os
            def restart():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=restart, daemon=True).start()
        else:
            self.send_error(404, "Not Found")

    def serve_file(self, path, mime):
        if os.path.exists(path):
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

if __name__ == '__main__':
    threading.Thread(target=ciclo_aggiornamento_api, daemon=True).start()
    threading.Thread(target=NewsPollingDaemon, daemon=True).start()
    try:
        porta = int(CONFIG.get('main', {}).get('porta_server', 8080))
        logging.info(f"Avvio KioskServer sulla porta {porta}")
        HTTPServer(('0.0.0.0', porta), KioskServer).serve_forever()
    except Exception as e:
        logging.error(f"Errore critico avvio server: {e}")
