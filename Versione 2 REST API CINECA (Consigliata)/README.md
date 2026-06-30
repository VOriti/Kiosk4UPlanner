# Kiosk4Uplanner - Versione 2: REST API CINECA (Consigliata)

[⬅ Torna alla pagina principale](../README.md)

### 🧠 Come funziona la comunicazione API con CINECA
Questa versione abbandona l'interazione visiva con l'interfaccia grafica di U-Planner (nessun browser nascosto che fa scraping). Il server Python si comporta come un vero e proprio "client", interrogando direttamente i database di CINECA tramite le **REST API ufficiali**.

Per comunicare con i server, Python esegue un Login inviando Username, Password e un parametro chiamato `realm` (che per CINECA corrisponde al codice univoco **`clienteId`** del tuo Ateneo). In risposta, CINECA consegna un **Bearer Token**: una lunga stringa crittografata che funge da "lasciapassare" per leggere i dati.

Il demone Python gestisce:
* Autenticazione: Gestisce il login e il rinnovo automatico del Bearer Token (Self-Healing).
* Data Handling: Interroga l'endpoint /Impegni/getImpegniCalendario inviando il contesto del dipartimento.
* Persistenza: Utilizza un database locale (stato_impegni.json) per mantenere memoria degli eventi "Annullati" o "Spostati" anche dopo il riavvio del server.
* Filtro Intelligente: Scarica il contesto completo dell'ateneo e filtra localmente le aule basandosi sulla variabile ID_EDIFICIO.

**La logica "Self-Healing":**
Per motivi di sicurezza, il Token di CINECA scade dopo 14 giorni. Invece di usare un timer (che si resetterebbe a ogni riavvio del Raspberry), il nostro server Python sfrutta una logica di "cura automatica" basata sugli errori HTTP. 
Quando il server prova a scaricare i dati delle aule e si accorge che il Token è scaduto (ricevendo indietro un errore di sistema **HTTP 401 - Unauthorized**), non va in crash. Al contrario, riconosce l'errore, mette in pausa l'aggiornamento, riesegue istantaneamente il Login in background per ottenere un Token fresco e ritenta la lettura. Questo rende il sistema perpetuo e totalmente esente da manutenzione manuale.

### 🚀 Funzionalità API

* **Leggerezza Assoluta:** Il Kiosk avvia unicamente una pagina web locale alleggerita. L'utilizzo di RAM e CPU del Raspberry Pi viene drasticamente ridotto rispetto alla Versione 1.
* **Sistema Perpetuo:** Nessun rinnovo manuale dei token di sicurezza. Python intercetta le scadenze e rinnova l'accesso senza mai interrompere il servizio.
* **Layout Unificato e Responsive:** Un solo file `remoto.html` renderizza la dashboard per il monitor 40" dell'atrio (Fullscreen), per i PC degli uffici (Doppia colonna) e si adatta in modo nativo su Smartphone e Tablet comprimendosi a colonna singola.
* **Menu Fluttuante a Scomparsa (Info Badge):** Un menu rapido e interattivo integrato nella UI che espone link utili (Calendario, GitHub, Licenza) scomparendo elegantemente per non rubare spazio su schermo (a comparsa laterale su PC, ed espansione verticale su Mobile).
* **Immunità agli Aggiornamenti:** Eventuali modifiche grafiche, banner istituzionali o manutenzioni dell'interfaccia Angular di U-Planner non romperanno mai la dashboard, poiché i dati viaggiano esclusivamente su un protocollo dati (JSON) che resta invariato.
* **Mapping Dinamico Edifici:** Grazie alla DEBUG_MODE, il sistema può auto-mappare tutti gli edifici disponibili con un semplice riavvio, eliminando la necessità di cercare manualmente gli ID nel DB di CINECA.
* **Gestione Annullamenti:** Il sistema traccia i cambiamenti in tempo reale (spostamenti di aula/orario o annullamenti) e li rende persistenti sul disco.
* **Layout CSS a "Compressione Automatica":** Il frontend (remoto.html) utilizza Flexbox per garantire che tutte le card siano sempre visibili senza bisogno di scroll, comprimendosi dinamicamente in base al numero di lezioni.

### 🏗️ Architettura del Sistema

Il progetto si compone di soli 3 elementi fondamentali:
1. **`server_api.py` (Il Motore):** Server HTTP Python. Si autentica in automatico su CINECA, interroga gli impegni del giorno, mappa i dati e li serve sulla porta `8080`.
2. **`remoto.html` (La UI):** Unica Web App in Dark Mode. Mantiene l'orologio, riproduce le locandine e disegna le aule attingendo ai dati del server.
3. **`~/.xinitrc` (L'Avvio):** Script standard di Linux che lancia l'ambiente grafico e apre Chromium in modalità Kiosk puntando a `http://localhost:8080/remoto.html`.

### 🛠️ Passaggi Iniziali da Fare (Quick Start)
1. **Configurazione Backend**: Inserisci username, password e clienteId nel file `server_api.py`.
2. **Configurazione Frontend**: Personalizza testi, link e loghi nel blocco `CONFIG_APP` all'inizio del file `remoto.html`.
3. **Impostazione Avvio Automatico**: Inserisci i comandi di autostart per fare in modo che il Raspberry Pi carichi tutto all'accensione (se si usa in produzione come Kiosk).

---

### 🛠️ Installazione Dettagliata (Versione API)

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
└── dashboard_aule/
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

**💡 Tips per Configurazione dei parametri**

Per il corretto funzionamento del sistema, è necessario configurare i parametri identificativi del proprio contesto universitario.

##### 1. Recupero API_REALM (clienteId)
Questo codice identifica l'istanza univoca dell'Ateneo su U-Planner.
1. Apri la pagina di login del portale U-Planner del tuo ateneo da browser PC.
2. Apri gli Strumenti per Sviluppatori (F12) e seleziona la scheda **Rete (Network)**.
3. Effettua il login.
4. Cerca tra le richieste (filtra per "login") quella chiamata `login?include=user`.
5. Seleziona la richiesta, vai nella scheda **Risposta (Response)** e copia il valore associato alla chiave `"clienteId"`.

##### 2. Recupero ID_EDIFICIO
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

#### 4. Personalizzazione Frontend (`remoto.html`)
È possibile adattare facilmente la schermata alle proprie esigenze modificando il blocco `CONFIG_APP` che si trova nelle primissime righe del file `remoto.html`:

```javascript
const CONFIG_APP = {
    titoloSede: "Impegni Aule", // Titolo che appare in alto a sinistra
    urlLogo: "/logo.png", // Lascia vuoto ("") per nasconderlo
    intervalloAggiornamento: 5000,
    messaggioNessunaLezione: "Nessun impegno attivo programmato per la giornata.",
    messaggioErroreRete: "Connessione persa col Server API.",
    // Impostazioni per il carosello di locandine
    pausaTraCaroselli: 180000, // Pausa in millisecondi tra un carosello e l'altro (default 3 minuti)
    esposizioneLocandina: 15000, // Durata esposizione per ogni singola locandina in millisecondi
    // LINK MENU A SCOMPARSA (Info Badge)
    urlCalendario: "https://unipv.prod.up.cineca.it/calendarioPubblico/linkCalendarioId=5e3d320d8409120018939b0a", // Inserisci il calendario della tua sede
    urlRepo: "https://github.com/VOriti/Kiosk4Uplanner", // Lascia invariato per rispetto licenza Attribution
    urlLicenza: "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.it", // Lascia invariato per rispetto licenza ShareAlike
    autore: "Vincenzo Oriti",
    emailAutore: "vincenzo.oriti@unipv.it"
};
```

Basta compilare questi campi con i propri dati per avere l'interfaccia personalizzata senza toccare il codice strutturale.

#### 5. Autostart (`~/.xinitrc`, `raspi-config` e `~/.bashrc`)
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
