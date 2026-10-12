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
* **Gestione Centralizzata (Nuovo in v4):** Un pannello di amministrazione accessibile via web (`/admin`) permette di configurare la dashboard in tempo reale (colori, loghi, ticker, avvisi) da remoto, senza mai riavviare o usare il terminale.
* **Ticker Notizie e Locandine (Nuovo in v4):** Integrazione nativa di un feed scorrevole orizzontale o verticale per mostrare notizie (estraibili da qualsiasi RSS o endpoint REST) e un carosello di locandine pubblicitarie, interamente gestibili dal pannello.
* **Layout Unificato e Responsive:** Un solo file `remoto.html` renderizza la dashboard per il monitor 40" dell'atrio (Fullscreen), per i PC degli uffici (Doppia colonna) e si adatta in modo nativo su Smartphone e Tablet comprimendosi a colonna singola.
* **Menu Fluttuante a Scomparsa (Info Badge):** Un menu rapido e interattivo integrato nella UI che espone link utili e permette di disabilitare il carosello locandine sul proprio dispositivo locale (es. PC Ufficio) senza interferire col monitor del Kiosk.
* **Immunità agli Aggiornamenti:** Eventuali modifiche grafiche, banner istituzionali o manutenzioni dell'interfaccia Angular di U-Planner non romperanno mai la dashboard, poiché i dati viaggiano esclusivamente su un protocollo dati (JSON) che resta invariato.
* **Mapping Dinamico Edifici:** Grazie alla DEBUG_MODE, il sistema può auto-mappare tutti gli edifici disponibili con un semplice riavvio, eliminando la necessità di cercare manualmente gli ID nel DB di CINECA.
* **Gestione Avanzata degli Stati (P e C):** Distingue nativamente gli eventi Pubblicati (P) dai Confermati (C) tramite indicatori visivi e permette di nascondere gli eventi non definitivi.
* **Risoluzione Indisponibilità:** Identifica e mostra la causale reale per cui un'aula è indisponibile, evitando le vecchie diciture generiche (es. "Attività programmata").
* **Gestione Annullamenti e Modifiche Live:** Gli eventi "Annullati" (A) dal gestionale vengono intercettati automaticamente; il sistema traccia inoltre i cambiamenti in tempo reale (spostamenti di aula/orario) e li rende persistenti sul disco.
* **Layout CSS a "Compressione Automatica":** Il frontend (remoto.html) utilizza Flexbox per garantire che tutte le card siano sempre visibili senza bisogno di scroll, comprimendosi dinamicamente in base al numero di lezioni.

### 🏗️ Architettura del Sistema

Il progetto si compone di elementi fondamentali:
1. **`server_api.py` (Il Motore):** Server HTTP Python. Si autentica in automatico su CINECA, interroga gli impegni del giorno, mappa i dati, scarica i feed RSS/REST e serve l'interfaccia sulla porta `8080`.
2. **`remoto.html` (La UI):** Unica Web App in Dark Mode. Mantiene l'orologio, riproduce le locandine e disegna le aule attingendo ai dati del server. Riceve istruzioni per ricaricarsi in tempo reale ("Hot-Reload").
3. **`admin.html` (Il Pannello Admin):** Interfaccia riservata per gestire la configurazione e salvarla su disco.
4. **`~/.xinitrc` (L'Avvio Kiosk):** Script standard di Linux che si occupa di lanciare il server Python in background, aprire l'ambiente grafico e lanciare Chromium a tutto schermo in modalità Kiosk all'accensione del dispositivo.

---

### 🛠️ Installazione Dettagliata (Passo-Passo)

In questa sezione ti guideremo passo-passo attraverso le seguenti fasi:
1. **Requisiti e Dipendenze:** Installazione dei pacchetti necessari.
2. **Copia e Posizionamento dei File:** Corretto posizionamento della cartella di progetto e degli script.
3. **Autostart e Modalità Kiosk:** Configurazione dell'avvio automatico di Python e Chromium al boot.
4. **Configurazione Base:** Inserimento delle credenziali per collegarsi alle API di CINECA.
5. **Personalizzazione Grafica:** Utilizzo del Pannello di Amministrazione web.
6. **Riavvio e Spegnimento:** Impostazione dei cronjob per salvaguardare il dispositivo spegnendolo automaticamente ad una certa ora (e riaccendendolo ad un'altra).
7. **Uso della Porta 80 (Opzionale):** Come evitare di dover inserire la porta nell'URL.

#### 1. Requisiti e Dipendenze (Raspberry Pi OS Lite)
Oltre all'ambiente grafico base, per questa versione sono necessarie alcune librerie Python per le chiamate HTTP e la lettura dei file di configurazione (YAML).

Esegui questo comando per installare in un solo colpo tutto il necessario:
```bash
sudo apt update
sudo apt install --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox unclutter chromium python3 python3-requests python3-yaml dos2unix -y
```

#### 2. Copia e Posizionamento dei File
Scarica o clona il progetto e posiziona la cartella `dashboard_aule` direttamente nella tua home directory.
**Attenzione:** il file nascosto `.xinitrc` va posizionato *fuori* dalla cartella `dashboard_aule`, direttamente nella tua radice utente.
La struttura finale (sostituendo `vincenzo` col tuo utente) dovrà essere la seguente:
```text
/home/vincenzo/
├── .xinitrc               <-- Script di avvio ambiente X11 (fondamentale)
└── dashboard_aule/
    ├── server_api.py      <-- Demone Python
    ├── remoto.html        <-- Dashboard pubblica
    ├── admin.html         <-- Pannello di Amministrazione
    ├── config.yaml        <-- File di configurazione
    ├── kiosk.log          <-- (Generato in automatico) Log dell'applicazione
    ├── server_api_sys.log <-- (Generato in automatico) Log del server
    └── locandine/         <-- (Opzionale) Immagini JPG per lo slideshow
```

#### 3. Autostart e Modalità Kiosk (`.bashrc` e `.xinitrc`)
Per fare in modo che il Raspberry accenda il monitor, avvii Python e lanci la webapp a tutto schermo automaticamente ad ogni accensione senza richiedere tastiere:
1. Attiva il "Console Autologin" eseguendo `sudo raspi-config` (Sotto *System Options* -> *Boot / Auto Login* -> *Console Autologin*).
2. Apri il file `~/.bashrc` e aggiungi questa singola riga alla fine:
   ```bash
   [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
   ```
3. Assicurati che il file `~/.xinitrc` fornito nel repository sia posizionato nella tua home directory. Lo script contenuto al suo interno (se lo apri) è già configurato per disabilitare il risparmio energetico dello schermo, lanciare in background `server_api.py` e infine lanciare `chromium` a tutto schermo in modalità Kiosk incognito verso il server locale.

#### 4. Configurazione Base ( da admin panel o da `config.yaml`)
A partire dalla versione 4.0, tutta la configurazione strutturale (credenziali CINECA comprese) è stata spostata all'interno del file `config.yaml`.
Puoi procedere in due modi:
- **Pannello Grafico:** Apri il file `config.yaml` con un editor di testo e imposta solo `admin_attivo: true`, poi riavvia il server e infine collegati al Pannello di Amministrazione web (`http://[IP_DEL_RASPBERRY]:8080/admin`). Da qui puoi modificare al volo l'interfaccia e le credenziali CINECA comprese.

- **Modifica Manuale:** Apri il file `config.yaml` con un editor di testo e compila la primissima sezione `api_cineca` (inserendo username, password, realm, id_edificio, anno_accademico_id e contesto_id) seguendo le precise istruzioni commentate all'interno del file.

**💡 Procedura per il Recupero dei parametri CINECA (Strumenti per Sviluppatori / F12)**

I parametri identificativi di CINECA U-Planner (`realm`, `anno_accademico_id`, `contesto_id`) possono essere recuperati facilmente analizzando il traffico di rete del browser durante l'uso del portale web U-Planner del proprio Ateneo:

- **Recupero `realm` (Cliente ID dell'Ateneo):**
  1. Apri la pagina di login del portale U-Planner del tuo ateneo (es. `https://[ateneo].prod.up.cineca.it/`) dal browser sul PC.
  2. Apri gli Strumenti per Sviluppatori premendo **F12** (oppure tasto destro sulla pagina -> *Ispeziona*, o `Ctrl+Shift+I` / `Cmd+Option+I`).
  3. Seleziona la scheda **Rete (Network)** e attiva il filtro **Fetch/XHR** per isolare le chiamate API.
  4. Effettua l'accesso inserendo le tue credenziali.
  5. Cerca tra le chiamate di rete la richiesta di autenticazione (solitamente denominata `login?include=user` o `login`).
  6. Clicca sulla richiesta e apri la sottoscheda **Risposta (Response)**: copia il valore alfanumerico associato alla chiave `"clienteId"` (o `"realm"`), composto da 24 caratteri esadecimali (es. `5a6734b248e4aa0cdeaaf875`).
  *Metodo alternativo:* In qualsiasi chiamata successiva verso le API CINECA, seleziona la richiesta, apri la scheda **Intestazioni (Headers)** e copia il valore dell'header di richiesta `X-Realm`.

- **Recupero `anno_accademico_id` (ID Anno Accademico):**
  1. All'interno del portale U-Planner, accedi alla visualizzazione del calendario/pianificazione delle lezioni o aule per l'anno accademico d'interesse.
  2. Con gli Strumenti per Sviluppatori (**F12**) aperti sulla scheda **Rete (Network)** (filtro **Fetch/XHR**), digita `getImpegniCalendario` nella casella di filtro/ricerca.
  3. Seleziona la richiesta POST denominata `getImpegniCalendario` (se non appare, cambia vista di calendario, giorno o settimana per forzare una richiesta).
  4. Clicca sulla sottoscheda **Payload** (o *Carico utile / Richiesta*).
  5. Individua il parametro **`annoAccademicoId`** e copia la stringa esadecimale di 24 caratteri (es. `5e1553cac831d600172af6d0`).
  *Metodo alternativo:* Cerca la chiamata all'endpoint `AnniAccademici` (GET) e nella scheda **Risposta (Response)** individua l'anno accademico attivo copiando il relativo valore `"id"` o `"_id"`.

- **Recupero `contesto_id` (ID Contesto / Dipartimento):**
  1. Nel portale U-Planner, seleziona la struttura didattica o dipartimento di competenza per visualizzarne gli impegni.
  2. Con la scheda **Rete (Network)** aperta (filtro **Fetch/XHR**), seleziona la medesima chiamata POST `getImpegniCalendario`.
  3. Nella sottoscheda **Payload** (o *Carico utile / Richiesta*), individua il parametro **`contestoId`** e copia la stringa esadecimale di 24 caratteri (es. `5b97788424deec000e171a8f`).
  *Metodo alternativo:* Filtra per `Contesti` nella scheda Rete: nella risposta JSON troverai l'elenco dei contesti/strutture con i corrispondenti identificativi `"id"`.

- **Recupero `id_edificio`:**
  1. Apri `config.yaml` e imposta `debug_mode: true` (oppure attivalo dal Pannello Admin). Riavvia il server.
  2. Attendi un ciclo di aggiornamento completo (circa 1 minuto).
  3. Leggi il log di sistema eseguendo `cat /home/vincenzo/dashboard_aule/kiosk.log`. Troverai una riga speciale denominata "🕵️ DEBUG MAPPA EDIFICI" con tutti i codici numerici dei palazzi del tuo ateneo.
  4. Ricopia l'ID del tuo palazzo dentro `config.yaml` e rimetti `debug_mode: false`.

*Nota:* Tutti questi identificativi possono essere inseriti sia a mano nel file `config.yaml`, sia comodamente tramite il **Pannello di Amministrazione Web** (`/admin`) nei rispettivi campi all'interno della sezione *Credenziali e Connessione CINECA*.


#### 5. Personalizzazione Grafica (file YAML o Pannello Admin)
A partire dalla Versione 4.0 non è più necessario modificare `remoto.html` per cambiare l'aspetto del Kiosk, perché tutte le impostazioni sono state unificate nel file `config.yaml`. Il file può essere modificato a mano o tramite il pannello di amministrazione web:
- Avvia il server Python.
- Attiva l'admin panel modificando il parametro `admin_attivo` in `true` nel file `config.yaml`.
- Riavvia il server Python e attendi che la dashboard si ricarichi sul monitor.
- Dal tuo PC, apri un browser e vai all'indirizzo `http://[IP_DEL_RASPBERRY]:8080/admin`.
- Da questo comodo pannello web potrai accendere il carosello locandine, attivare il footer per le news (con indirizzi RSS e colori personalizzati) e modificare tutti i testi. Cliccando su "Salva", il Kiosk recepirà le modifiche e si ricaricherà automaticamente ("Hot Reload").

#### 6. Riavvio e spegnimento

**Modalità Semplice:** Funziona su tutte le board anche economiche (ad es. Orange Pi Zero 3).

È possibile impostare un cronjob che spenga la board ad un determinato orario.
Ad esempio, se il palazzo chiude alle 20:00, si imposta la board per spegnersi alle 19:30.

Il portinaio alle 20:00 toglierà corrente dalla ciabatta e quando la riaccenderà alle 7:00 del mattino successivo la board si riavvierà.

Per configurare lo spegnimento programmato, apri il terminale della board ed entra nella modifica dei cronjob come amministratore digitando:
```bash
sudo crontab -e
```
Al primo avvio potrebbe chiederti quale editor di testo utilizzare (ti suggerisco di premere `1` per scegliere `nano`).
Scorri fino in fondo al file e aggiungi la seguente riga per far spegnere il sistema tutti i giorni alle 19:30 in punto:
```bash
30 19 * * * /sbin/poweroff
```
Salva il file (su nano si fa con `CTRL+O` seguito da `Invio`) ed esci (`CTRL+X`). 
Il sistema ora si spegnerà in modo sicuro ogni giorno all'orario stabilito, prevenendo così la corruzione della scheda SD dovuta al taglio "brutale" dell'alimentazione da parte del portinaio.

**Modalità avanzata: RTC (Real-Time Clock)**
Su alcune board avanzate, come il Pi 5, è possibile installare un modulo RTC (Real-Time Clock) hardware per gestire oltre allo spegnimento, anche un riavvio ad un determinato orario, evitando del tutto l'uso della ciabatta. Ci sono molte guide su come farlo online.

#### 7. Come usare la porta 80 per evitare di dover inserire [IP]:[porta]

Di default il server risponde sulla porta `8080` (es. `http://192.168.1.50:8080` o `http://totem.unipv.it:8080`). Se desideri che gli utenti possano accedere digitando unicamente l'indirizzo IP o il nome DNS (es. `http://192.168.1.50` o `http://totem.unipv.it`), è necessario utilizzare la porta HTTP standard `80`.

Su Linux tutte le porte inferiori alla 1024 sono **porte privilegiate** riservate all'utente `root`: se si imposta semplicemente la porta `80` in `config.yaml` senza i permessi necessari, il server Python fallirà l'avvio con l'errore `PermissionError: [Errno 13] Permission denied`, causando un errore `ERR_CONNECTION_REFUSED` nel browser.

Per abilitare la porta 80 sono disponibili tre metodi:

* **Metodo 1 (Consigliato): Port Redirection con `iptables`**  
  È il metodo più pulito e consigliato: il server Python rimane in ascolto sulla porta non privilegiata `8080` (senza toccare permessi di sistema), mentre il firewall del kernel Linux reindirizza in modo trasparente tutto il traffico in arrivo sulla porta 80 verso la porta 8080.
  1. Mantieni `porta_server: 8080` nel file `config.yaml` (o nel pannello `/admin`).
  2. Sul terminale del Raspberry Pi, applica la regola di redirezione:
     ```bash
     sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
     ```
  3. Rendi persistente la regola anche dopo i riavvii della scheda:
     ```bash
     sudo apt install iptables-persistent -y
     sudo netfilter-persistent save
     ```
  > **Vantaggio:** Funzionano contemporaneamente sia `http://[IP]` sia `http://[IP]:8080`, e **non è necessario modificare** lo script `~/.xinitrc`.

* **Metodo 2: Assegnazione Capability a Python (`setcap`)**  
  Se preferisci che Python si metta direttamente in ascolto sulla porta 80, puoi concedere all'eseguibile di Python la capability Linux `CAP_NET_BIND_SERVICE`, che gli permette di aprire porte privilegiate anche se eseguito come utente standard.
  1. Dal terminale del Raspberry Pi, esegui:
     ```bash
     sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
     ```
  2. Modifica la porta impostando `porta_server: 80` all'interno di `config.yaml` o dalla sezione *Rete e Sicurezza* del pannello `/admin`.
  3. ⚠️ **Aggiorna `~/.xinitrc`:** Modifica l'ultima riga del file `~/.xinitrc` per far puntare Chromium alla nuova porta:
     ```bash
     # Sostituisci http://localhost:8080/remoto.html con:
     exec chromium --noerrdialogs --disable-infobars --kiosk --start-fullscreen --incognito http://localhost/remoto.html
     ```
  4. Riavvia la board con `sudo reboot`.

* **Metodo 3: Reverse Proxy con Nginx (Ambienti di Rete Strutturati)**  
  Se il Raspberry risiede in una rete universitaria o d'ufficio complessa, la soluzione di livello Enterprise consiste nell'installare **Nginx** sulla porta 80 e fargli inoltrare le richieste verso Python (che rimane sulla `8080`). Questo approccio è ideale anche se in futuro vorrai aggiungere la crittografia HTTPS con certificato SSL d'Ateneo.
  1. Installa Nginx:
     ```bash
     sudo apt install nginx -y
     ```
  2. Modifica la configurazione del sito predefinito (`sudo nano /etc/nginx/sites-available/default`) impostando il proxy pass nel blocco `location /`:
     ```nginx
     server {
         listen 80;
         server_name _;

         location / {
             proxy_pass http://127.0.0.1:8080;
             proxy_set_header Host $host;
             proxy_set_header X-Real-IP $remote_addr;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         }
     }
     ```
  3. Riavvia Nginx:
     ```bash
     sudo systemctl restart nginx
     ```

> ⚠️ **REGOLA D'ORO PER IL CAMBIO PORTA E `~/.xinitrc`:**  
> Qualsiasi sia la nuova porta scelta (sia la `80`, sia una porta alternativa come `12345`), ricordati che **se cambi la porta in `config.yaml` o su `/admin`, devi SEMPRE aggiornarla anche nell'ultima riga del file `~/.xinitrc`** (es. `http://localhost:12345/remoto.html`).  
> Se ti dimentichi di farlo, il server Python funzionerà, ma il monitor fisico del totem mostrerà una schermata bianca di errore `ERR_CONNECTION_REFUSED` perché continuerà a cercare la vecchia porta `8080`.  
> *(L'unica eccezione è il Metodo 1 con `iptables`, dove la porta interna resta 8080 e non richiede modifiche a `~/.xinitrc`).*


### 💾 Gestione Stato e Persistenza
Il sistema genera automaticamente il file `stato_impegni.json` nella cartella di progetto.
* **Reset manuale:** Se desideri "pulire" la memoria di tutti gli annullamenti o spostamenti salvati, basta eliminare il file con questo comando: 
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
* **Reset stato:** Se vuoi resettare gli annullamenti/spostamenti salvati cancella il file `stato_impegni.json`:
    ```bash
    rm /home/vincenzo/dashboard_aule/stato_impegni.json
    ```
