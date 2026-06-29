# Kiosk4Uplanner - Dashboard Kiosk Informativa

*Sviluppato per l'Università di Pavia (UNIPV)*

**Versione:** 2.0 | **Autore:** [Vincenzo Oriti](https://oriti.net) ([vincenzo.oriti@unipv.it](mailto:vincenzo.oriti@unipv.it)) | **Progetto:** [GitHub](https://github.com/VOriti/Kiosk4Uplanner) | **Licenza:** [CC BY-NC-SA 4.0](LICENSE.txt) ([Testo completo](https://creativecommons.org/licenses/by-nc-sa/4.0/))

---

Questo progetto trasforma un Raspberry Pi in una postazione **Kiosk informativa**, da installare negli atri di un polo universitario per mostrare a studenti e docenti lo stato di occupazione delle aule in tempo reale.

Ha principalmente tre funzioni:
- mostra **l'occupazione in tempo reale delle aule** del palazzo;
- ogni tot minuti **mostra eventuali locandine di eventi in corso o futuri**;
- **rende disponibili i dati su una pagina web all'interno della rete locale**. In questo modo, il personale può controllare l'occupazione corrente delle aule direttamente dal browser del proprio PC.

Il repository è diviso in **due versioni** indipendenti, per adattarsi ai livelli di accesso a disposizione della struttura:

* 📖 [**Versione 1: Scraping DOM (Senza API)**](#versione-1-scraping-dom-senza-api) - Soluzione fai-da-te. Intercetta l'interfaccia web originale iniettando codice tramite Chromium. Consigliata solo se non disponi di alcuna credenziale di accesso a CINECA." Ideale se *non* si dispone di un'utenza API CINECA. *Necessita di un calendario pubblico da aprire per fare lo scraping dei dati.*

* 🚀 [**Versione 2: REST API CINECA (Consigliata)**](#versione-2-rest-api-cineca-consigliata) - "Metodo 'Native'. Interroga direttamente il DB di CINECA. Scelta consigliata per stabilità e prestazioni. Include persistenza degli annullamenti, mappatura dinamica degli edifici e zero carico di rendering. *Necessita delle credenziali di accesso a U-Planner.*

## Quale versione scegliere?

| Funzionalità | Versione 1 (Scraping) | Versione 2 (REST API - Consigliata) |
| :--- | :--- | :--- |
| **Metodo** | Iniezione DOM (Chromium) | Chiamata nativa REST API |
| **Credenziali** | **Nessuna richiesta** | Richiede Account U-Planner |
| **Stabilità** | Bassa (dipende dal layout web) | Alta (protocollo JSON) |
| **Persistenza** | No (stato volatile) | **Sì (salvataggio locale e tag "annullato/spostato" per modifiche live)** |
| **Risorse Hardware** | Elevato (Chrome è pesante) | **Minimo (Python Script)** |
| **Stato del Progetto** | Legacy (Backup) | **Produzione (Standard)** |


## Versione 2: REST API CINECA (Consigliata)

### 🧠 Sotto il cofano: Come funziona la comunicazione API
Questa versione abbandona l'interazione visiva con l'interfaccia grafica di U-Planner (nessun browser nascosto che fa scraping). Il server Python si comporta come un vero e proprio "client", interrogando direttamente i database di CINECA tramite le **REST API ufficiali**.

Per comunicare con i server, Python esegue un Login inviando Username, Password e un parametro chiamato `realm` (che per CINECA corrisponde al codice univoco **`clienteId`** del tuo Ateneo). In risposta, CINECA consegna un **Bearer Token**: una lunga stringa crittografata che funge da "lasciapassare" per leggere i dati.

Il demone Python gestisce:
* Autenticazione: Gestisce il login e il rinnovo automatico del Bearer Token (Self-Healing).
* Data Handling: Interroga l'endpoint /Impegni/getImpegniCalendario inviando il contesto del dipartimento.
* Persistenza: Utilizza un database locale (stato_impegni.json) per mantenere memoria degli eventi "Annullati" o "Spostati" anche dopo il riavvio del server.
* Filtro Intelligente: Scarica il contesto completo dell'ateneo e filtra localmente le aule basandosi sulla variabile ID_EDIFICIO.

**La logica "Self-Healing" (Auto-cura):**
Per motivi di sicurezza, il Token di CINECA scade dopo 14 giorni. Invece di usare un timer (che si resetterebbe a ogni riavvio del Raspberry), il nostro server Python sfrutta una logica di "cura automatica" basata sugli errori HTTP. 
Quando il server prova a scaricare i dati delle aule e si accorge che il Token è scaduto (ricevendo indietro un errore di sistema **HTTP 401 - Unauthorized**), non va in crash. Al contrario, riconosce l'errore, mette in pausa l'aggiornamento, riesegue istantaneamente il Login in background per ottenere un Token fresco e ritenta la lettura. Questo rende il sistema perpetuo e totalmente esente da manutenzione manuale.

### 🚀 Funzionalità API

* **Leggerezza Assoluta:** Il Kiosk avvia unicamente una pagina web locale alleggerita. L'utilizzo di RAM e CPU del Raspberry Pi viene drasticamente ridotto rispetto alla Versione 1.
* **Sistema Perpetuo:** Nessun rinnovo manuale dei token di sicurezza. Python intercetta le scadenze e rinnova l'accesso senza mai interrompere il servizio.
* **Layout Unificato:** Un solo file `remoto.html` renderizza la dashboard sia per il monitor 40" dell'atrio (Fullscreen) sia per i PC degli uffici (Responsive a doppia colonna).
* **Immunità agli Aggiornamenti:** Eventuali modifiche grafiche, banner istituzionali o manutenzioni dell'interfaccia Angular di U-Planner non romperanno mai la dashboard, poiché i dati viaggiano esclusivamente su un protocollo dati (JSON) che resta invariato.
* **Mapping Dinamico Edifici:** Grazie alla DEBUG_MODE, il sistema può auto-mappare tutti gli edifici disponibili con un semplice riavvio, eliminando la necessità di cercare manualmente gli ID nel DB di CINECA.
* **Gestione Annullamenti:** Il sistema traccia i cambiamenti in tempo reale (spostamenti di aula/orario o annullamenti) e li rende persistenti sul disco.
* **Layout CSS a "Compressione Automatica":** Il frontend (remoto.html) utilizza Flexbox per garantire che tutte le card siano sempre visibili senza bisogno di scroll, comprimendosi dinamicamente in base al numero di lezioni.

### 🏗️ Architettura del Sistema

Il progetto si compone di soli 3 elementi fondamentali:
1. **`server_api.py` (Il Motore):** Server HTTP Python. Si autentica in automatico su CINECA, interroga gli impegni del giorno, mappa i dati e li serve sulla porta `8080`.
2. **`remoto.html` (La UI):** Unica Web App in Dark Mode. Mantiene l'orologio, riproduce le locandine e disegna le due colonne di aule attingendo ai dati del server.
3. **`~/.xinitrc` (L'Avvio):** Script standard di Linux che lancia l'ambiente grafico e apre Chromium in modalità Kiosk puntando a `http://localhost:8080/remoto.html`.

### 🛠️ Installazione (Versione API)

#### 1. Requisiti di Sistema (Raspberry Pi OS Lite)
Oltre all'ambiente grafico base, per questa versione è necessaria la libreria `requests` di Python per le chiamate HTTP.
```bash
sudo apt update
sudo apt install --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox unclutter chromium python3 python3-requests dos2unix -y
```

#### 2. Struttura delle Cartelle
Configura i file in questo percorso (sostituisci `vincenzo` col tuo utente):
```text
/home/vincenzo/
├── .xinitrc
├── dashboard_aule/
    ├── server_api.py
    ├── remoto.html
    ├── logo.png (opzionale - banner orizzontale)
    ├── kiosk.log (generato in automatico dal server)
    └── locandine/
        ├── 1.jpg (opzionale)
        └── 2.jpg (opzionale)
```

#### 3. Configurazione Credenziali (`server_api.py`)
Apri il file `server_api.py` con un editor di testo. Nelle primissime righe troverai un blocco dedicato alle costanti. Sostituisci i valori con le tue credenziali API:
```python
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
```

**💡 Tips per Configurazione dei parametri API**

Per il corretto funzionamento del sistema, è necessario configurare i parametri identificativi del proprio contesto universitario.

#### 1. Recupero API_REALM (clienteId)
Questo codice identifica l'istanza univoca dell'Ateneo su U-Planner.
1. Apri la pagina di login del portale U-Planner del tuo ateneo da browser PC.
2. Apri gli Strumenti per Sviluppatori (F12) e seleziona la scheda **Rete (Network)**.
3. Effettua il login.
4. Cerca tra le richieste (filtra per "login") quella chiamata `login?include=user`.
5. Seleziona la richiesta, vai nella scheda **Risposta (Response)** e copia il valore associato alla chiave `"clienteId"`.

#### 2. Recupero ID_EDIFICIO
Il sistema include uno script di discovery integrato che automatizza il recupero dei codici degli edifici.

1. Apri `server_api.py` e imposta `DEBUG_MODE = True`.
2. Riavvia il server con il comando:
  ```bash
  killall python3 && python3 /home/vincenzo/dashboard_aule/server_api.py &
  ```
3. Attendi il primo ciclo di aggiornamento.
4. Analizza il file di log con il comando:
  ```bash
  cat /home/vincenzo/dashboard_aule/kiosk.log
  ```
5. Cerca la riga che inizia con 🕵️ DEBUG MAPPA EDIFICI:
6. Individua il codice dell'edificio desiderato, aggiorna la variabile ID_EDIFICIO nel file server_api.py e imposta nuovamente DEBUG_MODE = False per mantenere il log pulito.

#### 4. Autostart (`~/.xinitrc`, `raspi-config` e `~/.bashrc`)
Dato che questa versione non usa il software di iniezione CDP, il file di avvio automatico è molto più pulito. Carica il file `~/.xinitrc` presente nel repository.

Ricordati di attivare il Console Autologin tramite `raspi-config` e di richiamare `startx` dal file `~/.bash_profile` (o `~/.bashrc`) per lanciare il server grafico all'avvio:
   ```bash
   [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
   ```

### 💾 Gestione Stato e Persistenza
Il sistema genera automaticamente il file `stato_impegni.json` nella cartella di progetto.
* **Reset manuale:** Se desideri "pulire" la memoria di tutti gli annullamenti o spostamenti salvati, basta eliminare il file: 
  `rm /home/vincenzo/dashboard_aule/stato_impegni.json`
* **Log:** Il file `kiosk.log` è lo strumento principale per il debug. 

### 🔧 Troubleshooting e Manutenzione (V2)

* **Verifica stato server:** Se la dashboard non carica i dati, verifica che il demone sia attivo:
    ```bash
    ps aux | grep server_api.py
    ```
* **Log di sistema:** Consulta il log per errori di autenticazione o API:
    ```bash
    tail -f /home/vincenzo/dashboard_aule/kiosk.log
    ```
* **Problemi di formattazione (Caratteri strani/Errori):** Se il file Python è stato modificato su Windows, pulisci i caratteri di fine riga:
    ```bash
    dos2unix /home/vincenzo/dashboard_aule/server_api.py
    ```
* **Reset stato:** Se vuoi resettare gli annullamenti/spostamenti salvati:
    ```bash
    rm /home/vincenzo/dashboard_aule/stato_impegni.json
    ```

---
---

## Versione 1: Scraping DOM (Senza API)

### Sotto il cofano
Dal punto di vista tecnico, è una soluzione progettata per estrarre, formattare e trasmettere i dati dal sistema CINECA U-Planner. **Carica un calendario pubblico già esistente e ne converte i dati in un'interfaccia Kiosk bypassando i controlli anti-bot**: in sostanza risolve i classici problemi di estrazione dati da piattaforme blindate (blocchi Cloudflare, Errori 502/403 Bad Gateway e le limitazioni della sandbox delle estensioni) sfruttando il **Chrome DevTools Protocol (CDP)** per manipolare il DOM in tempo reale direttamente nel "Main World" del browser, azzerando il carico di rete anomalo ed eludendo i sistemi anti-bot.

### ⚙️ Funzionalità Avanzate

* **Bypass Cloudflare & Angular:** Sfrutta la sessione legittima del browser Chromium in esecuzione per leggere la griglia originale di U-Planner.
* **Aggiornamento Dati (Hard Reset):** Il sistema ricarica automaticamente la pagina di CINECA a intervalli regolari (es. ogni 30 min) per recepire i cambi di aula dell'ultimo minuto fatti dalle segreterie, re-iniettando l'interfaccia istantaneamente.
* **Layout Kiosk Adattivo (CSS Parametrico):** Interfaccia in *Dark Mode* istituzionale, le cui grandezze sono parametriche e modificabili direttamente dal codice sorgente.
* **Interfaccia Remota Indipendente:** Web App per gli uffici (`remoto.html`) con layout a CSS Grid. Presenta due colonne a scorrimento indipendente, header "sticky" (incollati) e scrollbar personalizzate.
* **Digital Signage & Banner:** Possibilità di esporre un banner/logo istituzionale in cima alla dashboard e di caricare locandine (`.jpg`) che appariranno ciclicamente a tutto schermo con dissolvenza incrociata.
* **Motore di Parsing Intelligente:** Riconosce le "Aule Fantasma" negli eventi spot, formatta e ripulisce le stringhe generate da CINECA eliminando parentesi e codici superflui senza tranciare informazioni vitali.
* **Logging Centralizzato & Notifiche Toast:** Tutti i log di sistema vengono scritti su un unico file (`kiosk.log`). Durante gli aggiornamenti in background, il monitor fisico mostra notifiche a comparsa (Toast) senza interrompere la visione.
* **Bypass Sicurezza (CORS & PNA):** Server e Browser configurati per eludere i blocchi di "Private Network Access" e Mixed Content di Chromium, garantendo un flusso dati fluido e senza pop-up grigi bloccanti.

### 🏗️ Architettura del Sistema

Il progetto si compone di 5 elementi che lavorano in sinergia:
1. **`~/.xinitrc` (L'Avvio):** Lancia l'ambiente X11 (Openbox), ruota il monitor, avvia Chromium con flag di massima sicurezza (`--incognito`, `--disable-web-security`, `--disable-notifications`) e apre la porta locale di debug (9222).
2. **`iniettore.py` (Il Demone):** Un processo Python H24. Sorveglia la porta 9222. Quando Chromium ricarica la pagina per l'Hard Reset, attende il rendering di Angular e inietta via WebSocket il nostro cruscotto.
3. **`cruscotto.js` (Il Cervello):** Inietta il foglio di stile (CSS), oscura l'app originale, estrapola aule e docenti, gestisce i caroselli delle immagini, genera le notifiche a schermo e invia i dati al server locale.
4. **`server.py` (Il Ponte):** Server HTTP Python (porta `8080`). Assolve le pretese CORS di Chromium, tiene i dati in RAM (Zero Usura SD) e serve la pagina remota, il logo e le locandine alla rete locale.
5. **`kiosk.log` (La Scatola Nera):** File di testo in cui Iniettore e Server scrivono in tempo reale eventi, iniezioni e messaggi di errore.

### 🛠️ Installazione

#### 1. Requisiti di Sistema (Raspberry Pi OS Lite / Debian)
Si consiglia un'installazione minima priva dell'ambiente Desktop (no PIXEL/GNOME).

```bash
sudo apt update
sudo apt install --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox unclutter chromium python3 python3-websocket dos2unix -y
```

#### 2. Struttura delle Cartelle
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

#### 3. Configurazione File
Modifica esclusivamente i blocchi di configurazione iniziali:
* **`~/.xinitrc`**: Inserisci l'URL pubblico di CINECA U-Planner e l'output video corretto per `xrandr` (es. `HDMI-1` o `HDMI-A-1`).
* **`cruscotto.js`**: Parametri `CONFIG` (testi da omettere, timer hard-reset) e `CONFIG_UI` (colori e grandezza font, URL del logo).
* **`remoto.html`**: Personalizza i testi di benvenuto e l'URL del logo nella variabile `CONFIG_APP`.
* **`iniettore.py` / `server.py`**: Intervalli di attesa e porte.

#### 4. Autostart
Usa `raspi-config` per impostare il Console Autologin.
Aggiungi in fondo a `~/.bash_profile` (o `~/.bashrc`):
```bash
[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
```

### 🖼️ Utilizzo del Digital Signage

* **Banner Fisso:** Carica un'immagine `logo.png` nella cartella principale. Comparirà automaticamente in alto su entrambi i monitor (Kiosk e Uffici).
* **Carosello Locandine:** Salva le immagini come `1.jpg`, `2.jpg` (fino a 4) nella cartella `locandine/`. Appariranno a schermo ciclicamente.

### 📡 Accesso Remoto per Uffici

Aprire dal PC (in LAN) l'indirizzo: `http://<IP_DEL_RASPBERRY>:8080`.
La Web App si riconnette in automatico se la centralina viene riavviata e offre uno scorrimento delle aule fluido e indipendente (due colonne).

### 🔧 Sysadmin & Troubleshooting

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