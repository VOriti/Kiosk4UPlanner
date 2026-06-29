#!/bin/bash
# ============================================================================
# CONFIGURAZIONE AVVIO GRAFICO E KIOSK (VERSIONE API)
# Modifica queste variabili per adattare l'installazione al tuo ambiente
# ============================================================================

# 1. Nome fisico della porta video (scoprilo con: DISPLAY=:0 xrandr | grep " connected")
NOME_MONITOR="HDMI-1"

# 2. Orientamento del monitor fisico: "normal" (orizzontale), "right" o "left" (verticale)
ROTAZIONE_MONITOR="normal"

# 3. Percorso assoluto in cui risiede il progetto (senza slash finale)
DIR_PROGETTO="/home/vincenzo/dashboard_aule" #sostitusci 'vincenzo' con il tuo nome utente

# ============================================================================
# AVVIO SISTEMA
# ============================================================================

# Disabilita screen saver e risparmio energetico
xset s off
xset s noblank
xset -dpms

# Ruota il monitor fisico
xrandr --output $NOME_MONITOR --rotate $ROTAZIONE_MONITOR

# Nasconde il cursore del mouse dopo mezzo secondo di inattività
unclutter -idle 0.5 -root &

# Avvia il gestore di finestre minimale OpenBox (fondamentale per gestire i bordi e la finestra)
openbox-session &

# Avvia il server API Python in background e salva eventuali errori nel log temporaneo
python3 $DIR_PROGETTO/server_api.py > /tmp/server_api.log 2>&1 &

# Attende 5 secondi per dare il tempo a Python di fare il primo login a CINECA
sleep 5

# Lancia Chromium a tutto schermo, disabilitando gli avvisi di sicurezza,
# e lo punta all'interfaccia unificata servita dal nostro server locale
exec chromium --noerrdialogs --disable-infobars --kiosk --start-fullscreen --incognito http://localhost:8080/remoto.html