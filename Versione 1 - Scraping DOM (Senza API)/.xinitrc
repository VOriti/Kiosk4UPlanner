#!/bin/bash
# ============================================================================
# CONFIGURAZIONE AVVIO GRAFICO E KIOSK
# Modifica queste variabili per adattare l'installazione al tuo ambiente
# ============================================================================

# 1. L'indirizzo pubblico del calendario CINECA U-Planner del dipartimento
URL_UPLANNER="https://unipv.prod.up.cineca.it/calendarioPubblico/linkCalendarioId=5e3d320d8409120018939b0a"

# 2. Orientamento del monitor fisico: "normal" (orizzontale), "right" o "left" (verticale)
ROTAZIONE_MONITOR="normal"

# 3. Percorso assoluto in cui è stato clonato il progetto (senza slash finale)
DIR_PROGETTO="/home/vincenzo/dashboard_aule"

# ============================================================================
# MOTORE DI AVVIO (NON MODIFICARE SE NON NECESSARIO)
# ============================================================================

# Disabilita lo screensaver, lo spegnimento dello schermo e il risparmio energetico
xset s off
xset s noblank
xset -dpms

# Imposta la rotazione dello schermo (su Raspberry Pi di default l'uscita è HDMI-1)
xrandr --output HDMI-1 --rotate $ROTAZIONE_MONITOR

# Nasconde il cursore del mouse dopo 0.1 secondi di inattività
unclutter -idle 0.1 -root &

# Avvia il window manager super-leggero (gestione finestre base)
openbox-session &

# Avvia il micro-server web in background per fornire i dati in JSON ai PC degli uffici
python3 $DIR_PROGETTO/server.py &

# Avvia l'iniettore CDP in background. Dorme 60 secondi per dare tempo alla CPU
# di renderizzare la pesante app Angular originale, poi esegue l'override grafico.
python3 $DIR_PROGETTO/iniettore.py > /tmp/iniettore.log 2>&1 &

# Lancia Chromium in modalità Kiosk pura. Apre l'URL di CINECA e sblocca la porta 
# locale 9222 per permettere al nostro iniettore Python di prendere il controllo.
exec chromium --noerrdialogs --disable-infobars --kiosk --disable-web-security --user-data-dir=/tmp/chromium_kiosk --disable-features=BlockInsecurePrivateNetworkRequests --remote-debugging-port=9222 --remote-allow-origins="*" "$URL_UPLANNER"