#!/usr/bin/env python3
"""
Kiosk4Uplanner - DASHBOARD KIOSK INFORMATIVA
Kindly developed for University of Pavia (UNIPV)
-----------------------------------------------------
Una soluzione per trasformare un Raspberry Pi in una postazione
Kiosk per il monitoraggio aule in tempo reale.
-----------------------------------------------------
Nessuna dipendenza esterna richiesta per i client.
----------------------------------------------------
Author Information / Informazioni sull'autore
@author  Vincenzo Oriti
@contact vincenzo.oriti@unipv.it
@personal_page https://oriti.net
---------------------------------------------------------
Project information / Informazioni sul progetto
@project_page https://github.com/VOriti/Kiosk4Uplanner
@version 1.0
@license CC BY-NC-SA 4.0
@license_url https://creativecommons.org/licenses/by-nc-sa/4.0/    
"""
# ============================================================================
# INIETTORE CDP (Chrome DevTools Protocol) - IL "ROBOT"
# Questo script agisce in background all'avvio della postazione Kiosk.
# Attende che Chromium abbia caricato la pagina ufficiale (lenta e pesante),
# dopodiché inietta il codice JavaScript personalizzato sfruttando la porta
# di debug locale. Questo ci garantisce i privilegi di "Main World" per eludere
# i controlli anti-bot e i firewall di Cloudflare (Errore 502/403).
# ============================================================================

import urllib.request
import json
import time
import os
import websocket
import logging

# ============================================================================
# CONFIGURAZIONE INIETTORE
# ============================================================================
PORTA_DEBUG = 9222

# Parola chiave nell'URL della pagina per identificare la scheda (tab) corretta
URL_TARGET = "unipv"

# Nome del file contenente il layout grafico e la logica da iniettare
NOME_FILE_JS = "cruscotto.js"

# Tempo di attesa (in secondi) affinché l'interfaccia di CINECA finisca il rendering.
# L'hardware impiega tempo ad avviare la pagina Angular di U-Planner sia all'avvio
# sia dopo ogni Hard Reset programmato.
ATTESA_ANGULAR = 45

# Frequenza (in secondi) con cui il robot controlla se la dashboard è ancora attiva.
INTERVALLO_CONTROLLO = 10

# Ricava dinamicamente il percorso assoluto in cui si trova questo script.
# Molto utile se il repo viene clonato in cartelle diverse da quella di default.
DIR_CORRENTE = os.path.dirname(os.path.abspath(__file__))
PERCORSO_JS = os.path.join(DIR_CORRENTE, NOME_FILE_JS)

# ============================================================================
# CONFIGURAZIONE LOGGING CENTRALIZZATO E NOTIFICHE
# Tutti i messaggi finiranno nel file "kiosk.log"
# ============================================================================
FILE_LOG = os.path.join(DIR_CORRENTE, 'kiosk.log')
logging.basicConfig(
    filename=FILE_LOG,
    level=logging.INFO,
    format='%(asctime)s - [INIETTORE] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def invia_notifica_schermo(ws, messaggio, tipo="info"):
    """Inietta un comando JS per far comparire il box colorato sul monitor."""
    try:
        msg_pulito = messaggio.replace("'", "\\'") # Evita errori di sintassi JS
        codice = f"if(window.mostraNotifica) mostraNotifica('{msg_pulito}', '{tipo}');"
        ws.send(json.dumps({
            "id": 99,
            "method": "Runtime.evaluate",
            "params": {"expression": codice}
        }))
    except Exception:
        pass

def ottieni_websocket_url():
    """
    Interroga la porta di debug locale di Chromium per farsi restituire
    l'indirizzo WebSocket segreto della scheda che stiamo cercando.
    """
    try:
        # Il timeout evita che lo script si blocchi se Chromium si sta riavviando
        req = urllib.request.urlopen(f'http://127.0.0.1:{PORTA_DEBUG}/json', timeout=2)
        tabs = json.loads(req.read().decode('utf-8'))
        for tab in tabs:
            # Cerca la pagina attiva che contiene il target nel link
            if tab.get('type') == 'page' and URL_TARGET in tab.get('url', ''):
                return tab['webSocketDebuggerUrl']
    except Exception:
        return None

if __name__ == "__main__":
    logging.info("Avviato servizio di monitoraggio continuo H24.")
    
    # ========================================================================
    # CICLO INFINITO DI MONITORAGGIO E INIEZIONE
    # L'iniettore ora non muore più dopo il primo avvio. Se rileva che la
    # pagina si è ricaricata (Hard Reset), inietta nuovamente il codice.
    # ========================================================================
    while True:
        ws_url = ottieni_websocket_url()
        
        if ws_url:
            try:
                # Timeout di 5s per evitare blocchi in caso di ricaricamento esatto
                ws = websocket.create_connection(ws_url, timeout=5)
                
                # 1. CONTROLLO: Verifica se l'overlay è già presente a schermo
                ws.send(json.dumps({
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "!!document.getElementById('kiosk-overlay')"
                    }
                }))
                
                risposta = json.loads(ws.recv())
                gia_iniettato = risposta.get('result', {}).get('result', {}).get('value', False)
                
                # 2. INIEZIONE (GOD MODE): Avviene solo se la pagina è "pulita"
                if not gia_iniettato:
                    logging.info(f"Pagina CINECA originale rilevata. Attendo {ATTESA_ANGULAR} secondi per il caricamento...")
                    
                    # Notifica a schermo visibile agli utenti!
                    invia_notifica_schermo(ws, "Aggiornamento dati in corso...", "info")
                    
                    time.sleep(ATTESA_ANGULAR) 
                    
                    # LETTURA DEL CODICE JAVASCRIPT
                    # Legge dal disco ad ogni iniezione. In questo modo le modifiche fatte
                    # al file .js si applicano in automatico al primo Hard Reset!
                    # errors="ignore" è un salvavita: impedisce allo script Python di bloccarsi 
                    # se nel file .js viene inserito un carattere non UTF-8 puro (es. lettere accentate).
                    try:
                        with open(PERCORSO_JS, "r", encoding="utf-8", errors="ignore") as f:
                            js_code = f.read()
                    except FileNotFoundError:
                        logging.error(f"Errore: File {NOME_FILE_JS} non trovato nel percorso {DIR_CORRENTE}.")
                        ws.close()
                        time.sleep(INTERVALLO_CONTROLLO)
                        continue

                    # Invia il codice JS a Chromium simulando l'inserimento manuale nella
                    # Console per gli Sviluppatori. Prende istantaneamente il controllo del monitor.
                    ws.send(json.dumps({
                        "id": 2,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": js_code
                        }
                    }))
                    ws.recv() 
                    
                    logging.info("Iniezione completata con successo! Il DOM è stato sovrascritto.")
                    
                    # Notifica verde di conferma a schermo
                    invia_notifica_schermo(ws, "Sistema allineato", "successo")
                    
                ws.close()
            except Exception:
                # Disconnessioni momentanee durante un reload sono normali, passa oltre in silenzio
                pass
                
        # Mette a riposo la CPU per non saturare le risorse del Raspberry Pi
        time.sleep(INTERVALLO_CONTROLLO)