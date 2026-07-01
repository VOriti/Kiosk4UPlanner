#!/usr/bin/env python3
import json
import os
import logging
import time
import threading
import datetime
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================================
# CONFIGURAZIONE API CINECA 
# ============================================================================
API_USERNAME = "INSERISCI_LA_TUA_USERNAME_DI_UP"
API_PASSWORD = "INSERISCI_LA_TUA_PASSWORD_DI_UP"
API_REALM    = "INSERISCI_IL_CLIENTE_ID_DEL_TUO_ATENEO"   # Es. "vzdv2mcs8ffre6sed856fsa86kgg5" Per scoprire il tuo realm, apri la console admin di UPlanner e copia il valore del campo "clienteId" nella sezione "Realm" (in alto a sinistra). Per altri atenei, chiedere al supporto CINECA il codice corretto o attivare la debug mode per far girare uno script di discovery che stampa i codici nel log su kiosk.log
ID_EDIFICIO  = "INSERISCI_L_ID_EDIFICIO"   # Es. "05" per  Palazzo San Felice in UNIPV. Per altri atenei, chiedere al supporto CINECA il codice corretto o attivare la debug mode per far girare uno script di discovery che stampa i codici nel log su kiosk.log
INTERVALO_AGGIORNAMENTO = 300  # secondi (default 5 minuti)
URL_BASE     = "https://unipv.prod.up.cineca.it/api" # URL_BASE = "https://cineca.prod.up.cineca.it/api" è l'URL di base per le API CINECA di UPlanner. Sostituire "cineca" prima di prod con il proprio ateneo

URL_LOGIN    = f"{URL_BASE}/Utenti/login"
# Usiamo l'endpoint corretto scoperto dai log della console admin
URL_IMPEGNI  = f"{URL_BASE}/Impegni/getImpegniCalendario" 

# ============================================================================
# CONFIGURAZIONE DEBUG
# ============================================================================
DEBUG_MODE = False # Imposta su True solo quando devi mappare nuovi edifici o vedere la struttura dei dati. In modalità debug, il server logga tutti gli impegni ricevuti e stampa una mappa degli edifici trovati.

# ============================================================================
# CONFIGURAZIONE SERVER LOCALE E LOG
# ============================================================================
PORTA_SERVER = 8080
PERCORSO_BASE = '/home/vincenzo/dashboard_aule' #modifica 'vincenzo' con il tuo nome utente di sistema. Es. '/home/mario/dashboard_aule'
FILE_LOG = os.path.join(PERCORSO_BASE, 'kiosk.log')

logging.basicConfig(
    filename=FILE_LOG,
    level=logging.INFO,
    format='%(asctime)s - [API SERVER] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

memoria_dati = []
lock_memoria = threading.Lock()
token_cineca = None
storico_impegni = {}
data_storico = None

def carica_stato():
    global storico_impegni
    if os.path.exists(os.path.join(PERCORSO_BASE, 'stato_impegni.json')):
        with open(os.path.join(PERCORSO_BASE, 'stato_impegni.json'), 'r', encoding='utf-8') as f:
            storico_impegni = json.load(f)
    
    #Fix per evitare che impegni annullati rimangano nel file di stato per 24 ore finendo per essere visualizzati come "ANNULLATO" anche il giorno successivo.
    # Ottiene la mezzanotte di oggi in formato UTC (timestamp)
    ora_attuale = datetime.datetime.now(datetime.timezone.utc)
    mezzanotte_oggi = ora_attuale.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    # Mantiene solo gli eventi che finiscono DOPO la mezzanotte di oggi
    storico_impegni = {k: v for k, v in storico_impegni.items() if v['timestamp_fine'] > mezzanotte_oggi}

# Chiama questa funzione subito dopo aver inizializzato le variabili globali
carica_stato()

def salva_stato():
    with open(os.path.join(PERCORSO_BASE, 'stato_impegni.json'), 'w', encoding='utf-8') as f:
        json.dump(storico_impegni, f, indent=4)

def effettua_login():
    global token_cineca
    logging.info("Richiesta di un nuovo Token a CINECA (Admin) in corso...")
    payload = {
        "username": API_USERNAME, 
        "password": API_PASSWORD, 
        "realm": API_REALM,
        "clientId": API_REALM 
    }
    try:
        risposta = requests.post(URL_LOGIN, json=payload, timeout=10)   
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
            
            # FILTRO EDIFICIO
            aule = item.get('aule', [])
            edifici_impegno = [a.get('edificio', {}).get('codice') for a in aule]
            if ID_EDIFICIO not in edifici_impegno and ID_EDIFICIO != "":
                continue

            str_inizio = item.get('dataInizio', '').replace('Z', '+00:00')
            str_fine = item.get('dataFine', '').replace('Z', '+00:00')
            dt_inizio = datetime.datetime.fromisoformat(str_inizio)
            dt_fine = datetime.datetime.fromisoformat(str_fine)
            
            # Parsing titolo robusto
            evento = item.get('evento', {})
            titolo_raw = (item.get('nome') or evento.get('nome') or evento.get('dettaglioDidattico', {}).get('nome') or "Attività programmata")
            
            nuovi_estratti[id_imp] = {
                "id": id_imp,
                "orario": f"{dt_inizio.astimezone().strftime('%H:%M')} - {dt_fine.astimezone().strftime('%H:%M')}",
                "titolo": titolo_raw.strip(),
                "docente": f"{item.get('docenti', [{}])[0].get('cognome', '')} {item.get('docenti', [{}])[0].get('nome', '')}".strip() if item.get('docenti') else "Dipartimento",
                "aula": aule[0].get('descrizione', 'Da definire').strip() if aule else "Da definire",
                "inCorso": (dt_inizio <= ora_attuale <= dt_fine),
                "timestamp_inizio": dt_inizio.timestamp(),
                "timestamp_fine": dt_fine.timestamp(),
                "cancellato": False,
                "avviso": ""
            }
        except Exception:
            continue

# Aggiornamento stato con logica di persistenza spostamenti
    for id_nuovo, imp_nuovo in nuovi_estratti.items():
        if id_nuovo not in storico_impegni:
            storico_impegni[id_nuovo] = imp_nuovo
        else:
            imp_storico = storico_impegni[id_nuovo]
            
            # Verifica se c'è stato un cambiamento (Aula o Orario)
            cambiata_aula = imp_storico['aula'] != imp_nuovo['aula']
            cambiato_orario = imp_storico['orario'] != imp_nuovo['orario']
            
            # Se è cambiato qualcosa e non abbiamo già un avviso di spostamento
            if (cambiata_aula or cambiato_orario) and not imp_storico.get('avviso', '').startswith("Spostato"):
                # Salviamo le info "vecchie" prima di sovrascriverle
                vecchia_aula = imp_storico['aula']
                vecchio_orario = imp_storico['orario']
                imp_storico['avviso'] = f"Spostato (da {vecchia_aula} ore {vecchio_orario})"
            
            # Aggiorniamo i dati correnti (mantenendo l'avviso se esiste già)
            imp_nuovo['avviso'] = imp_storico.get('avviso', "")
            imp_storico.update(imp_nuovo)

    # Gestione Annullamenti
    for id_storico, imp_storico in storico_impegni.items():
        if id_storico not in nuovi_estratti and imp_storico['timestamp_fine'] > ora_attuale.timestamp():
            imp_storico["cancellato"] = True
            imp_storico["avviso"] = "ANNULLATO"

    # Salva le modifiche su file dopo aver aggiornato il dizionario
    salva_stato()

    dati_puliti = [imp for imp in storico_impegni.values() if imp['timestamp_fine'] > ora_attuale.timestamp() or imp['inCorso']]
    dati_puliti.sort(key=lambda x: x['timestamp_inizio'])
    return dati_puliti

def ciclo_aggiornamento_api():
    global token_cineca, memoria_dati
    logging.info("🚀 Avviato demone API CINECA (Modalità Admin Autenticata).")
    
    while True:
        try:
            if not token_cineca:
                if not effettua_login():
                    time.sleep(120)
                    continue
            
            headers = { 
                "Authorization": token_cineca, # Nessun Bearer, passiamo il token pulito
                "Content-Type": "application/json",
                "X-Realm": API_REALM 
            }            
            
            oggi = datetime.datetime.now(datetime.timezone.utc)
            inizio_giornata = oggi.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            fine_giornata = oggi.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")

            # Payload identico a quello inviato dalla console admin
            payload = {
                "limit": 150,
                "dataInizio": inizio_giornata,
                "dataFine": fine_giornata,
                "annoAccademicoId": "5e1553cac831d600172af6d0",
                "mostraImpegniSenzaAula": False,
                "nascondiIndisponibilitaParziali": False,
                "contestoId": "5b97788424deec000e171a8f"
            }
            
            logging.info(f"DEBUG: Richiesta impegni (Admin) a {URL_IMPEGNI}")
            risposta = requests.post(URL_IMPEGNI, json=payload, headers=headers, timeout=15)
            
            if risposta.status_code == 401:
                logging.error("❌ Token scaduto o non valido (401). Forzo il rinnovo.")
                token_cineca = None
                time.sleep(2)
                continue
            elif risposta.status_code == 200:
                dati_grezzi = risposta.json()
                # --- BLOCCO DEBUG CONDIZIONALE ---
                if DEBUG_MODE:
                    # Logghiamo quanti eventi abbiamo ricevuto
                    logging.info(f"🕵️ DEBUG: Ricevuti {len(dati_grezzi)} impegni grezzi.")
                    
                    # Logghiamo i dettagli di ogni impegno per capire se la struttura è quella attesa
                    for i, imp in enumerate(dati_grezzi):
                        titolo = imp.get('nome') or imp.get('evento', {}).get('nome') or "N/A"
                        id_aula = imp.get('aule', [{}])[0].get('id', 'N/A')
                        logging.info(f"🕵️ DEBUG [{i}]: Trovato '{titolo}' | Aula ID: {id_aula}")

                    # Mappa edifici (quella che avevamo già)
                    edifici_scoperti = set()
                    for imp in dati_grezzi:
                        for a in imp.get('aule', []):
                            ed = a.get('edificio', {})
                            if ed.get('codice'):
                                edifici_scoperti.add(f"{ed.get('codice')} = {ed.get('descrizione')}")
                    logging.info(f"🕵️ DEBUG MAPPA EDIFICI: {edifici_scoperti}")
                # ---------------------------------
                with lock_memoria:
                    memoria_dati = estrai_e_formatta_dati(dati_grezzi)
                logging.info(f"✅ Dati ricevuti! Trovati {len(memoria_dati)} impegni per l'edificio {ID_EDIFICIO}.")
            else:
                logging.error(f"❌ Errore HTTP {risposta.status_code}: {risposta.text[:100]}")
                
        except Exception as e:
            logging.error(f"❌ Errore critico nel ciclo API: {e}")
        
        time.sleep(INTERVALO_AGGIORNAMENTO)

class KioskServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass 
        
    def do_GET(self):
        if self.path == '/dati.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with lock_memoria: self.wfile.write(json.dumps(memoria_dati).encode('utf-8'))
        elif self.path in ['/', '/remoto.html']:
            self.serve_file(os.path.join(PERCORSO_BASE, 'remoto.html'), 'text/html')
        elif self.path == '/logo.png': 
            self.serve_file(os.path.join(PERCORSO_BASE, 'logo.png'), 'image/png')
        elif self.path.startswith('/locandine/'): 
            self.serve_file(os.path.join(PERCORSO_BASE, 'locandine', os.path.basename(self.path)), 'image/jpeg')

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
    try:
        HTTPServer(('0.0.0.0', PORTA_SERVER), KioskServer).serve_forever()
    except Exception as e:
        logging.error(f"Errore critico avvio server: {e}")