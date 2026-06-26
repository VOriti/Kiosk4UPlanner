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
# KIOSK SERVER - CENTRALINA DI SMISTAMENTO DATI E LOCANDINE
# ============================================================================

import json
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

PORTA_SERVER = 8080
PERCORSO_BASE = '/home/vincenzo/dashboard_aule'
memoria_dati = []

# ============================================================================
# CONFIGURAZIONE LOGGING
# ============================================================================
FILE_LOG = os.path.join(PERCORSO_BASE, 'kiosk.log')
logging.basicConfig(
    filename=FILE_LOG,
    level=logging.INFO,
    format='%(asctime)s - [SERVER] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class KioskServer(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass 

    # ========================================================================
    # GESTIONE CORS E PRIVATE NETWORK ACCESS (PNA)
    # Rilascia il lasciapassare a Chromium per farsi inviare i dati in locale
    # senza far comparire il popup di autorizzazione a schermo.
    # ========================================================================
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_POST(self):
        global memoria_dati
        if self.path == '/update':
            length = int(self.headers.get('Content-Length', 0))
            if length > 0:
                try:
                    post_data = self.rfile.read(length)
                    memoria_dati = json.loads(post_data.decode('utf-8'))
                except Exception as e:
                    pass
            
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()

    def do_GET(self):
        if self.path == '/dati.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
            self.wfile.write(json.dumps(memoria_dati).encode('utf-8'))

	# --- BLOCCO PER IL BANNER ---
        elif self.path == '/logo.png':
            filepath = os.path.join(PERCORSO_BASE, 'logo.png')
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Private-Network', 'true')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        # ----------------------------------
            
        elif self.path.startswith('/locandine/'):
            filepath = os.path.join(PERCORSO_BASE, self.path.lstrip('/'))
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                
        elif self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            filepath_html = os.path.join(PERCORSO_BASE, 'remoto.html')
            try:
                with open(filepath_html, 'rb') as f:
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.wfile.write(b"<h1>Errore: File remoto.html non trovato sul Raspberry.</h1>")

if __name__ == '__main__':
    logging.info(f"📡 Server Kiosk avviato sulla porta {PORTA_SERVER}...")
    try:
        HTTPServer(('0.0.0.0', PORTA_SERVER), KioskServer).serve_forever()
    except KeyboardInterrupt:
        logging.warning("\n🛑 Server arrestato manualmente.")