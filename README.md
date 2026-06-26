# Kiosk4Uplanner - Dashboard Kiosk Informativa

*Sviluppato per l'Università di Pavia (UNIPV)*

**Versione:** 1.0 | **Autore:** [Vincenzo Oriti](https://oriti.net) ([vincenzo.oriti@unipv.it](mailto:vincenzo.oriti@unipv.it)) | **Progetto:** [GitHub](https://github.com/VOriti/Kiosk4Uplanner) | **Licenza:** [CC BY-NC-SA 4.0](LICENSE.txt) ([Testo completo](https://creativecommons.org/licenses/by-nc-sa/4.0/))

---

Questo progetto trasforma un Raspberry Pi in una postazione **Kiosk informativa**, da installare negli atri di un polo universitario per mostrare a studenti e docenti lo stato di occupazione delle aule in tempo reale. 

Oltre a pilotare il monitor pubblico, il Raspberry Pi funge da vera e propria "centralina" server: elabora i dati e li rende disponibili su una pagina web all'interno della rete locale. In questo modo, **il personale negli uffici può controllare l'occupazione corrente delle aule direttamente dal browser del proprio PC**, senza doversi alzare dalla scrivania o cercare il calendario pubblico di UPlanner.

### Sotto il cofano
Dal punto di vista tecnico, è una soluzione progettata per estrarre, formattare e trasmettere i dati dal sistema CINECA U-Planner. 
Risolve i classici problemi di estrazione dati da piattaforme blindate (blocchi Cloudflare, Errori 502/403 Bad Gateway e le limitazioni della sandbox delle estensioni) sfruttando il **Chrome DevTools Protocol (CDP)** per manipolare il DOM in tempo reale direttamente nel "Main World" del browser, azzerando il carico di rete anomalo ed eludendo i sistemi anti-bot.

---

## Funzionalità Avanzate

* **Bypass Cloudflare & Angular:** Sfrutta la sessione legittima del browser Chromium in esecuzione per leggere la griglia originale di U-Planner.
* **Aggiornamento Dati (Hard Reset):** Il sistema ricarica automaticamente la pagina di CINECA a intervalli regolari (es. ogni 30 min) per recepire i cambi di aula dell'ultimo minuto fatti dalle segreterie, re-iniettando l'interfaccia istantaneamente.
* **Layout Kiosk Adattivo (CSS Parametrico):** Interfaccia in *Dark Mode* istituzionale, le cui grandezze sono parametriche e modificabili direttamente dal codice sorgente.
* **Interfaccia Remota Indipendente:** Web App per gli uffici (`remoto.html`) con layout a CSS Grid. Presenta due colonne a scorrimento indipendente, header "sticky" (incollati) e scrollbar personalizzate.
* **Digital Signage & Banner:** Possibilità di esporre un banner/logo istituzionale in cima alla dashboard e di caricare locandine (`.jpg`) che appariranno ciclicamente a tutto schermo con dissolvenza incrociata.
* **Motore di Parsing Intelligente:** Riconosce le "Aule Fantasma" negli eventi spot, formatta e ripulisce le stringhe generate da CINECA eliminando parentesi e codici superflui senza tranciare informazioni vitali.
* **Logging Centralizzato & Notifiche Toast:** Tutti i log di sistema vengono scritti su un unico file (`kiosk.log`). Durante gli aggiornamenti in background, il monitor fisico mostra notifiche a comparsa (Toast) senza interrompere la visione.
* **Bypass Sicurezza (CORS & PNA):** Server e Browser configurati per eludere i blocchi di "Private Network Access" e Mixed Content di Chromium, garantendo un flusso dati fluido e senza pop-up grigi bloccanti.

---

## Architettura del Sistema

Il progetto si compone di 5 elementi che lavorano in sinergia:
1. **`~/.xinitrc` (L'Avvio):** Lancia l'ambiente X11 (Openbox), ruota il monitor, avvia Chromium con flag di massima sicurezza (`--incognito`, `--disable-web-security`, `--disable-notifications`) e apre la porta locale di debug (9222).
2. **`iniettore.py` (Il Demone):** Un processo Python H24. Sorveglia la porta 9222. Quando Chromium ricarica la pagina per l'Hard Reset, attende il rendering di Angular e inietta via WebSocket il nostro cruscotto.
3. **`cruscotto.js` (Il Cervello):** Inietta il foglio di stile (CSS), oscura l'app originale, estrapola aule e docenti, gestisce i caroselli delle immagini, genera le notifiche a schermo e invia i dati al server locale.
4. **`server.py` (Il Ponte):** Server HTTP Python (porta `8080`). Assolve le pretese CORS di Chromium, tiene i dati in RAM (Zero Usura SD) e serve la pagina remota, il logo e le locandine alla rete locale.
5. **`kiosk.log` (La Scatola Nera):** File di testo in cui Iniettore e Server scrivono in tempo reale eventi, iniezioni e messaggi di errore.

---

## Installazione

### 1. Requisiti di Sistema (Raspberry Pi OS Lite / Debian)
Si consiglia un'installazione minima priva dell'ambiente Desktop (no PIXEL/GNOME).

```bash
sudo apt update
sudo apt install --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox unclutter chromium-browser python3 python3-websocket dos2unix -y
```

### 2. Struttura delle Cartelle
Configura i file in questo percorso (sostituisci `vincenzo` col tuo utente):

```text
/home/vincenzo/dashboard_aule/
├── cruscotto.js
├── iniettore.py
├── server.py
├── remoto.html
├── logo.png (opzionale - banner orizzontale)
├── kiosk.log (generato in automatico)
└── locandine/
    ├── 1.jpg (opzionale)
    └── 2.jpg (opzionale)
```

### 3. Configurazione File
Modifica esclusivamente i blocchi di configurazione iniziali:
* **`~/.xinitrc`**: Inserisci l'URL pubblico di CINECA U-Planner e l'output video corretto per `xrandr` (es. `HDMI-1` o `HDMI-A-1`).
* **`cruscotto.js`**: Parametri `CONFIG` (testi da omettere, timer hard-reset) e `CONFIG_UI` (colori e grandezza font, URL del logo).
* **`remoto.html`**: Personalizza i testi di benvenuto e l'URL del logo nella variabile `CONFIG_APP`.
* **`iniettore.py` / `server.py`**: Intervalli di attesa e porte.

### 4. Autostart
Usa `raspi-config` per impostare il Console Autologin.
Aggiungi in fondo a `~/.bash_profile` (o `~/.bashrc`):
```bash
[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
```

---

## Utilizzo del Digital Signage

* **Banner Fisso:** Carica un'immagine `logo.png` nella cartella principale. Comparirà automaticamente in alto su entrambi i monitor (Kiosk e Uffici).
* **Carosello Locandine:** Salva le immagini come `1.jpg`, `2.jpg` (fino a 4) nella cartella `locandine/`. Appariranno a schermo ciclicamente.

---

## Accesso Remoto per Uffici

Aprire dal PC (in LAN) l'indirizzo: `http://<IP_DEL_RASPBERRY>:8080`.
La Web App si riconnette in automatico se la centralina viene riavviata e offre uno scorrimento delle aule fluido e indipendente (due colonne).

---

## Sysadmin & Troubleshooting

* **Monitoraggio in tempo reale:** Controlla lo stato vitale del Kiosk senza toccare il monitor:
  ```bash
  tail -f /home/vincenzo/dashboard_aule/kiosk.log
  ```
* **Testare le modifiche grafiche:** Se modifichi i colori o i margini in `cruscotto.js`, non serve riavviare il Raspberry. Fai ricaricare Chromium:
  ```bash
  killall chromium
  ```
* **Errore "No such file or directory" (\r):** Se sposti i file da Windows a Linux potresti importare i *Carriage Return*. Puliscili così:
  ```bash
  dos2unix /home/vincenzo/dashboard_aule/*.py
  ```
* **Lo schermo non ruota:** Identifica il nome esatto della tua porta video digitando `DISPLAY=:0 xrandr | grep " connected"` e aggiornalo in `~/.xinitrc`.