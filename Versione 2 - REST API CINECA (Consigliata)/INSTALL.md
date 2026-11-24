# Guida all'Installazione Passo-Passo (Versione 2 - REST API CINECA)

[⬅ Torna alla Presentazione della Versione 2](README.md) | [🏠 Torna alla Pagina Principale del Progetto](../README.md)

---

Questa guida operativa ti accompagna passo-passo nell'installazione, configurazione e messa in produzione del Kiosk informativo su **Raspberry Pi OS Lite** (o distribuzioni Linux Debian-based compatibili).

### 📑 Indice delle Fasi
1. [Requisiti e Dipendenze di Sistema](#1-requisiti-e-dipendenze-raspberry-pi-os-lite)
2. [Copia e Posizionamento dei File](#2-copia-e-posizionamento-dei-file)
3. [Autostart e Modalità Kiosk (.bashrc e .xinitrc)](#3-autostart-e-modalità-kiosk-bashrc-e-xinitrc)
4. [Configurazione Credenziali e Codici CINECA (Debug Mode o procedura F12)](#4-configurazione-credenziali-cineca)
5. [Personalizzazione Iniziale da Pannello Web o YAML](#5-personalizzazione-iniziale-file-yaml-o-pannello-admin)
6. [Rete e Porte Standard (Porta 80 e Porta 443 con iptables)](#6-rete-e-porte-standard-come-evitare-di-digitare-la-porta-nellurl)
7. [Configurazione HTTPS / SSL Nativo (Opzionale)](#7-configurazione-https--ssl-nativo-opzionale)
8. [Spegnimento Programmato e Risparmio Energetico](#8-spegnimento-programmato-e-risparmio-energetico)
9. [Verifica e Collaudo Finale](#9-verifica-e-collaudo-finale)

---

### 1. Requisiti e Dipendenze (Raspberry Pi OS Lite)
Oltre all'ambiente grafico minimale (Xorg e Openbox), per questa versione sono necessarie le librerie Python per le chiamate HTTP e la gestione dei file di configurazione YAML, nonché `openssl` per l'eventuale crittografia SSL.

Esegui questo comando per installare in un solo colpo tutto il necessario:
```bash
sudo apt update
sudo apt install --no-install-recommends xserver-xorg x11-xserver-utils xinit openbox unclutter chromium python3 python3-requests python3-yaml dos2unix openssl -y
```

> 💡 **Nota sui pacchetti:** Il modulo `ssl` utilizzato per la crittografia HTTPS in `server_api.py` fa già parte della Standard Library nativa di Python (`python3`), quindi non richiede ulteriori librerie pip. Il pacchetto di sistema `openssl` serve per generare o gestire i certificati crittografici `.pem`.

---

### 2. Copia e Posizionamento dei File
Scarica o clona il repository e posiziona la cartella `dashboard_aule` direttamente nella tua home directory.

⚠️ **Attenzione:** il file nascosto `.xinitrc` va posizionato *fuori* dalla cartella `dashboard_aule`, direttamente nella radice della tua home utente (`~/.xinitrc`).

La struttura finale (sostituendo `vincenzo` con il tuo effettivo nome utente) dovrà essere la seguente:
```text
/home/vincenzo/
├── .xinitrc               <-- Script di avvio ambiente X11 (fondamentale)
└── dashboard_aule/
    ├── server_api.py      <-- Demone Python
    ├── remoto.html        <-- Dashboard pubblica
    ├── admin.html         <-- Pannello di Amministrazione
    ├── config.example.yaml<-- Template di configurazione commentato
    ├── config.yaml        <-- File di configurazione (creato da config.example.yaml)
    ├── kiosk.log          <-- (Generato in automatico) Log dell'applicazione
    ├── server_api_sys.log <-- (Generato in automatico) Log del server
    └── locandine/         <-- (Opzionale) Immagini JPG per lo slideshow
```

> 💡 **Suggerimento permessi Windows/Linux:** Se hai modificato o copiato i file da un PC Windows, assicurati che i fine riga siano in formato Unix (LF) eseguendo:
> ```bash
> dos2unix /home/vincenzo/.xinitrc
> dos2unix /home/vincenzo/dashboard_aule/server_api.py
> chmod +x /home/vincenzo/.xinitrc
> ```

> 💡 **Nota sul percorso base (`percorso_base` in `config.yaml`):**  
> Di default, `server_api.py` rileva **automaticamente** la cartella in cui si trova, garantendo l'avvio immediato. Tuttavia, per mantenere la configurazione pulita e allineata, se il tuo utente Linux è diverso da `vincenzo` (ad esempio `pi` o `totem`), apri `config.yaml` e inserisci il tuo percorso effettivo nel campo:  
> `percorso_base: "/home/[tuo_utente]/dashboard_aule"`

---

### 3. Autostart e Modalità Kiosk (`.bashrc` e `.xinitrc`)
Per fare in modo che il Raspberry Pi accenda il monitor, avvii Python e lanci la webapp a tutto schermo automaticamente ad ogni accensione senza richiedere tastiera o login manuale, il sistema sfrutta una catena sequenziale:

#### 🔄 La Catena di Avvio del Kiosk (Come funziona)
```text
[ 🔌 Accensione Raspberry Pi ]
               │
               ▼
[ 1. Kernel & Systemd ] ──► Esegue l'Autologin sulla console (TTY1) come Utente designato
               │
               ▼
[ 2. ~/.bashrc ] ────────► Rileva la console TTY1 in assenza di ambiente grafico
                           ed esegue automaticamente il comando: startx
               │
               ▼
[ 3. ~/.xinitrc ] ───────► Inizializza l'ambiente grafico X11:
                           ├─ Disabilita lo screensaver e risparmio energetico (xset)
                           ├─ Nasconde il cursore del mouse inattivo (unclutter)
                           ├─ Lancia server_api.py in background (&)
                           ├─ Avvia il gestore finestre leggero (openbox)
                           └─ Avvia Chromium a tutto schermo (Kiosk) su http://localhost:8080/?kiosk=1
               │
               ▼
[ 🖥️ Dashboard Operativa a Schermo Intero ]
```

#### Configurazione Pratica:

1. **Abilita il Console Autologin:**  
   Esegui:
   ```bash
   sudo raspi-config
   ```
   Vai in *System Options* -> *Boot / Auto Login* -> seleziona **Console Autologin** (accesso automatico al terminale senza richiesta di password).

   > 👥 **Sistemi con più utenti (Quale utente viene avviato?):**  
   > Lo strumento `raspi-config` configura per l'autologin l'utente con cui sei attualmente collegato quando esegui il comando.  
   > Se sul Raspberry hai creato più account (es. un utente amministratore e un utente dedicato `totem`), hai due possibilità:
   > - **Metodo consigliato:** Esegui il login con l'utente desiderato per il totem e lancia da lì `sudo raspi-config`.
   > - **Modifica diretta con systemd:** Linux definisce l'utente di autologin nel file `/etc/systemd/system/getty@tty1.service.d/autologin.conf`. Puoi verificare o forzare il nome utente modificando il parametro `--autologin [NOME_UTENTE]`:
   >   ```bash
   >   sudo nano /etc/systemd/system/getty@tty1.service.d/autologin.conf
   >   ```

2. **Configura l'avvio di X11 in `~/.bashrc`:**  
   Apri il file `~/.bashrc` con un editor di testo (`nano ~/.bashrc`) e aggiungi questa riga alla fine del file:
   ```bash
   [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
   ```

3. **Verifica lo script `~/.xinitrc`:**  
   Assicurati che il file `~/.xinitrc` fornito nel repository sia posizionato nella tua home directory. Lo script è già preconfigurato per:
   - Disabilitare lo screensaver e il risparmio energetico dello schermo (DPMS).
   - Avviare il server Python `server_api.py` in background con watchdog e rotazione automatica del log `server_api_sys.log` a 5 MB.
   - Avviare il gestore finestre leggero `openbox`.
   - Lanciare `chromium` a tutto schermo in modalità Kiosk con il parametro `?kiosk=1` (che attiva automaticamente le locandine sul totem).

> ⚠️ **Aggiornamento da versioni precedenti:** Lo script `.xinitrc` include la rotazione automatica del log di sistema a 5 MB (`server_api_sys.log` ruotato in `.1`). Va ricopiato in `~/.xinitrc` su ogni Raspberry Pi (`cp "Versione 2 - REST API CINECA (Consigliata)/.xinitrc" ~/.xinitrc`).

> 📺 **Monitor Secondari, Smart TV e Digital Signage (`?kiosk=1`):**  
> Se colleghi alla dashboard altri schermi o Smart TV da corridoio (es. TV con browser integrato WebOS/Tizen, stick Android o PC remoti senza Raspberry Pi), assicurati di aprire l'URL aggiungendo il parametro **`?kiosk=1`** (es. `http://[IP_DEL_RASPBERRY]:8080/?kiosk=1` o `http://totem.unipv.it/?kiosk=1`).  
> In questo modo il dispositivo viene riconosciuto come postazione Kiosk e mostrerà a rotazione il carosello delle locandine a schermo intero (che per i normali utenti web da PC o smartphone è invece disattivato di default).

---

### 4. Configurazione Credenziali CINECA
Tutta la configurazione strutturale (credenziali e parametri CINECA compresi) risiede nel file `config.yaml` ed è gestibile sia da interfaccia grafica che manualmente:

- **Tramite Pannello Web (Consigliato):** Apri `config.yaml` (copiato da `config.example.yaml`), assicurati che `admin_attivo` sia `true`, avvia il server (`python3 server_api.py`) e dal tuo PC collegati a `http://[IP_DEL_RASPBERRY]:8080/admin` (scheda **⚙️ Sistema e Rete**).
- **Tramite Modifica Manuale:** Apri `config.yaml` con un editor (`nano config.yaml`) e compila la sezione `api_cineca` (`username`, `password`, `realm`, `anno_accademico_id`, `contesto_id`, `id_edificio`).

#### 🧭 A cosa corrispondono i 4 codici identificativi di CINECA U-Planner
Oltre a `username`, `password` e `url_base` (`https://[ateneo].prod.up.cineca.it/api`), U-Planner utilizza 4 codici identificativi che lavorano insieme in due passaggi (prima CINECA estrae gli impegni del *Contesto* e dell'*Anno Accademico*, poi il Kiosk filtra localmente le aule dell'*Edificio*):

| Parametro (`config.yaml`) | Formato Tipico | Obbligatorio | Cosa identifica in CINECA U-Planner |
| :--- | :--- | :---: | :--- |
| **`realm`** | 24 caratteri hex (`5a6734...`) | **Sì** | Il **`clienteId` univoco dell'intero Ateneo** su U-Planner. Non cambia mai nel tempo; può fornirlo direttamente l'help-desk di Ateneo oppure si ricava con `F12` al login. |
| **`anno_accademico_id`** | 24 caratteri hex (`5fefef...`) | **Sì** | L'identificativo interno dell'**Anno Accademico corrente** (es. `2026/2027`). **Va aggiornato una volta all'anno** (a inizio nuovo A.A., es. settembre). |
| **`contesto_id`** | 24 caratteri hex (`5b9778...`) | **Sì** | L'**ambito gestionale delle aule** su U-Planner: può essere un intero **Polo didattico** (es. *Polo Centrale / Polo B / Polo C*), un singolo *Dipartimento*, oppure un gruppo trasversale (*Aule Storiche*, *Aule Informatiche*). **Importante:** se nel tuo edificio fanno lezione più Dipartimenti, scegli sempre l'ID del **Polo** (e non del singolo Dipartimento), altrimenti vedrai solo le lezioni di quel Dipartimento! Senza `contesto_id` U-Planner restituisce `0` lezioni; inoltre circoscrive la risposta sotto il limite massimo di 500 impegni per chiamata. |
| **`id_edificio`** | Codice breve (`05`, `A1`, ecc.) | Opzionale (Consigliato) | Il codice del **singolo palazzo/plesso**. Filtra localmente gli impegni ricevuti dal Contesto mostrando solo le aule dell'edificio desiderato (se lasciato vuoto mostra tutte le aule dell'intero Contesto). |

Per trovare i codici hai a disposizione **due metodi equivalenti**:

---

#### 🕵️ Metodo 1 (Consigliato): Auto-Discovery guidata tramite `Debug Mode`
Una volta inseriti **`username`**, **`password`** e **`realm`** (fornito dall'help-desk o letto una tantum col Metodo 2 qui sotto), il Kiosk può interrogare direttamente CINECA e stampare nei log l'elenco completo con nomi e ID di tutti gli **Anni Accademici**, **Contesti** ed **Edifici** del tuo Ateneo:

1. Apri `/admin` → scheda **⚙️ Sistema e Rete** → tendina **🎓 Credenziali e Connessione CINECA**:
   - Compila `Username CINECA`, `Password CINECA`, `Realm` e `URL Base API`.
   - Spunta subito sotto il box informativo la voce **Abilita Debug Mode** (finché il Debug Mode è attivo il server ti permette di salvare anche lasciando vuoti Anno Accademico e Contesto).
   - Clicca su **⚡ Salva e Riavvia Demone** (oppure imposta `main.debug_mode: true` in `config.yaml` e riavvia il server).
2. Attendi circa 10 secondi e leggi le mappe generate in `kiosk.log` dal terminale del Raspberry Pi:
   ```bash
   grep "DEBUG MAPPA" ~/dashboard_aule/kiosk.log
   ```
3. Troverai stampate in chiaro le anagrafiche ufficiali del tuo Ateneo:
   - **`🕵️ DEBUG MAPPA ANNI ACCADEMICI RILEVATI`:** elenca ogni anno (es. `2026/2027 (cod. '2026') -> ID '5fefefdef4653b001808e636' [ANNO IN CORSO]`), segnalando automaticamente quale copre la data odierna.
   - **`🕵️ DEBUG MAPPA CONTESTI RILEVATI`:** elenca tutti i Poli, Dipartimenti e Aree del tuo Ateneo con codice, nome esteso e ID di 24 caratteri (es. `Codice 'Polo A' (Polo Centrale) -> ID '5b97788424deec000e171a8f'`).
4. Copia l'`ID` dell'Anno in corso e l'`ID` del tuo Contesto/Polo in `/admin` e salva. Al ciclo successivo (o riavviando) comparirà nel log anche la terza mappa, calcolata sugli impegni reali di una giornata con lezioni attive:
   - **`🕵️ DEBUG MAPPA EDIFICI RILEVATI`:** elenca i codici numerici/alfanumerici e i nomi di tutti i palazzi presenti nel Contesto (es. `Codice '05': Palazzo Centrale / San Felice`).
5. Inserisci il codice del tuo palazzo in **`ID Edificio`**, **togli la spunta da `Abilita Debug Mode`** (`debug_mode: false`) e salva definitivamente. *(Consulta anche [LEGENDA_LOG.md](LEGENDA_LOG.md) per il dettaglio completo dei messaggi di debug).*

---

#### 🌐 Metodo 2 (Alternativo e per trovare il `realm`): Strumenti Sviluppatore del Browser (`F12`)
Tutti i codici (incluso il **`realm`** iniziale dell'Ateneo qualora non ti sia stato comunicato dall'help-desk) possono essere letti analizzando dal PC il traffico di rete del portale web U-Planner del tuo Ateneo:

* **1. Recupero `realm` (Cliente ID dell'Ateneo):**
  1. Apri sul tuo PC la pagina di login del portale U-Planner del tuo Ateneo (es. `https://[ateneo].prod.up.cineca.it/`).
  2. Premi **F12** (o tasto destro → *Ispeziona*) e apri la scheda **Rete (Network)** attivando il filtro **Fetch/XHR**.
  3. Effettua l'accesso con le tue credenziali e clicca sulla richiesta `login` (o `login?include=user`).
  4. Apri la sottoscheda **Risposta (Response)** e copia la stringa di 24 caratteri esadecimali associata a **`"clienteId"`** (o `"realm"`, es. `5a6734b248e4aa0cdeaaf875`).  
     *(In alternativa: in qualunque chiamata successiva verso `/api/...`, apri la sottoscheda **Intestazioni / Headers** e copia il valore dell'header **`X-Realm`**).*

* **2. Recupero `anno_accademico_id` (ID Anno Accademico):**
  1. Dentro il portale U-Planner apri il calendario delle lezioni, seleziona l'anno accademico corrente e nella scheda **Rete (Fetch/XHR)** cerca **`getImpegniCalendario`** (cambia giorno o vista se non compare subito).
  2. Nella sottoscheda **Payload** (Richiesta), copia i 24 caratteri esadecimali del campo **`annoAccademicoId`** (es. `5fefefdef4653b001808e636`).  
     *(Suggerimento: se cerchi invece la chiamata GET `AnniAccademici` nella scheda Rete → Risposta, vedrai l'elenco completo degli anni con `"descrizione": "2026/2027"` e relativo `"id"`).*

* **3. Recupero `contesto_id` (ID Contesto — Polo / Dipartimento / Area):**
  1. Nel menu a tendina del contesto in alto sul portale U-Planner, seleziona il **Polo didattico** (consigliato per edifici condivisi da più Dipartimenti) oppure il Dipartimento/Area di competenza.
  2. Nella chiamata POST **`getImpegniCalendario`** → sottoscheda **Payload**, copia i 24 caratteri esadecimali del campo **`contestoId`** (es. `5b97788424deec000e171a8f`).  
     *(Suggerimento: cercando nella scheda Rete la chiamata GET `Contesti` → Risposta, puoi consultare la lista completa con `"codice"` — es. `"Polo A"` —, `"descrizione"` — es. `"Polo Centrale"` — e `"id"` per verificare a quale struttura corrisponde ciascun codice).*

* **4. Recupero `id_edificio` (Codice Palazzo):**
  1. Nella stessa chiamata POST **`getImpegniCalendario`**, apri la sottoscheda **Risposta (Response)** in un giorno con lezioni attive.
  2. Espandi un impegno qualsiasi → array **`aule`** → oggetto **`edificio`**: troverai **`"codice"`** (es. `"05"`, il valore da inserire in `id_edificio`) e **`"descrizione"`** (il nome del palazzo per conferma).

---

### 5. Personalizzazione Iniziale (File YAML o Pannello Admin)
Tutte le impostazioni visive e funzionali sono centralizzate nel file `config.yaml` e modificabili dal Pannello Web `/admin`:
1. Avvia il server Python (`python3 server_api.py`).
2. Verifica che `admin_attivo` sia impostato su `true`.
3. Dal browser del tuo PC o smartphone collegati a `http://[IP_DEL_RASPBERRY]:8080/admin`.
4. Dal pannello potrai:
   - Attivare o disattivare l'Avviso di Emergenza (Alert Giallo) in tempo reale.
   - Configurare il carosello locandine (intervallo secondi, orari di accensione).
   - Impostare i feed del Ticker Notizie (fino a 6 fonti RSS/REST con colori e pesi personalizzati).
   - Personalizzare colori, loghi istituzionali e titoli delle colonne.
5. Cliccando su **"💾 Salva Modifiche"**, il server aggiorna il file su disco e invia un segnale di "Hot Reload" a tutti i Kiosk collegati, che si aggiorneranno all'istante senza bisogno di riavvii.

---

### 6. Rete e Porte Standard: Come evitare di digitare la porta nell'URL
Di default il server risponde sulla porta HTTP `8080` (es. `http://192.168.1.50:8080`). Se desideri che gli utenti possano accedere digitando solo l'indirizzo IP o il nome DNS (es. `http://totem.unipv.it`), serve la porta standard `80`.

Su Linux tutte le porte inferiori a 1024 sono **porte privilegiate**: se provi ad impostare direttamente la porta `80` in `config.yaml` senza permessi speciali, Python fallirà l'avvio con l'errore `PermissionError: [Errno 13] Permission denied`, causando l'errore `ERR_CONNECTION_REFUSED` nel browser.

#### Metodo 1 (Consigliato): Port Redirection con `iptables` (Porta 80 e Porta 443)
È il metodo più pulito e flessibile: Python rimane in ascolto sulle sue porte non privilegiate (`8080` per HTTP e `8443` per HTTPS), mentre il kernel Linux reindirizza in modo trasparente il traffico standard verso di esse.

Esegui questo blocco completo di comandi sul Raspberry Pi:

```bash
# 1. Pulisci la tabella nat per rimuovere regole parziali precedenti:
sudo iptables -t nat -F

# 2. Reindirizzamento traffico da rete esterna (altri PC, smartphone, smart TV via LAN/Wi-Fi):
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 8443

# 3. Reindirizzamento traffico locale (test o browser Chromium a bordo del Raspberry Pi):
sudo iptables -t nat -A OUTPUT -p tcp -o lo --dport 80 -j REDIRECT --to-port 8080
sudo iptables -t nat -A OUTPUT -p tcp -o lo --dport 443 -j REDIRECT --to-port 8443

# 4. Rendi permanenti le regole anche dopo i riavvii:
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

> **Vantaggi del Metodo 1:**  
> - Funzionano contemporaneamente `http://[IP]`, `https://[IP]`, `http://[IP]:8080` e `https://[IP]:8443`.  
> - **Non richiede alcuna modifica** allo script `~/.xinitrc`.  
> - Per verificare le regole attive: `sudo iptables -t nat -L -n -v --line-numbers`.  
> - Per resettare le regole: `sudo iptables -t nat -F && sudo netfilter-persistent save`.

#### Metodo 2: Assegnazione Capability a Python (`setcap`)
Concede all'eseguibile Python il permesso di aprire porte privilegiate come utente normale:
```bash
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))
```
Imposta quindi `porta_server: 80` in `config.yaml`.  
⚠️ **Importante:** In questo caso **devi aggiornare anche l'ultima riga di `~/.xinitrc`** sostituendo `:8080` con l'indirizzo su porta 80 standard, altrimenti Chromium mostrerà schermata bianca `ERR_CONNECTION_REFUSED`.

#### Metodo 3: Reverse Proxy con Nginx
In reti strutturate d'ateneo, puoi installare un server Nginx sulla porta 80/443 che inoltri le chiamate al processo locale Python (`127.0.0.1:8080`).

---

### 7. Configurazione HTTPS / SSL Nativo (Opzionale)
A partire dalla versione 5.0, `server_api.py` integra il supporto nativo per la crittografia SSL/TLS in modalità **dual-thread** (ascolto contemporaneo su HTTP e HTTPS nello stesso processo), senza richiedere server esterni.

#### 1. Posizionamento o generazione dei certificati
Posiziona i certificati nella cartella `dashboard_aule/`:
- Certificato pubblico: `cert.pem`
- Chiave privata: `key.pem`

Se non possiedi un certificato ufficiale della CA d'Ateneo o Let's Encrypt, puoi generarne uno autofirmato per test con OpenSSL:
```bash
cd ~/dashboard_aule
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=kiosk.local"
```

#### 2. Abilitazione del servizio HTTPS
- **Dal Pannello `/admin`:** Vai nella scheda **⚙️ Sistema e Rete** → tendina **🔒 Server HTTPS (SSL Nativo)**, attiva la spunta **"Abilita Server HTTPS parallelo"**, imposta la porta (predefinita `8443`) e salva.
- **Da `config.yaml`:**
  ```yaml
  https:
    abilitato: true
    porta_https: 8443
    file_certificato: "cert.pem"
    file_chiave: "key.pem"
    forza_redirect_http: false
  ```

#### 3. Redirect automatico e Protezione Fail-Safe
Se desideri forzare l'uso di HTTPS per tutti i visitatori, imposta `forza_redirect_http: true`.
- **Fail-Safe anti-blocco:** Se i file del certificato o della chiave non vengono trovati, il server **disabilita automaticamente il redirect** e continua a servire la pagina in chiaro via HTTP, impedendo blocchi totali del totem.
- **Bypass locale per il Totem:** Le richieste provenienti da `localhost` e `127.0.0.1` non vengono mai reindirizzate a HTTPS. In questo modo il browser Chromium locale a bordo del Raspberry Pi continua a comunicare in locale evitando avvisi di certificati autofirmati.
- **Porte standard:** Se il traffico arriva tramite il port forwarding di `iptables` (porta 80 -> 8080), il redirect reindirizza direttamente a `https://[IP_O_DNS]` sulla porta 443 standard senza mostrare numeri di porta nell'URL.

> 📲 **Best Practice per QR Code e Materiale Stampato:**  
> Se devi stampare adesivi, cartelli o locandine con un QR Code che rimanda alla dashboard, imposta sempre l'URL con prefisso **`http://`** (es. `http://totem.unipv.it`):
> - **Funziona subito:** Chi scansiona il codice accede immediatamente via HTTP, anche se i certificati SSL non sono ancora stati installati sulla macchina.
> - **Zero ristampe future:** Non appena riceverai e installerai i certificati ufficiali (e abiliterai `forza_redirect_http: true`), il server Python dirotterà in automatico tutti gli smartphone su `https://`. Non dovrai mai ristampare il materiale cartaceo!
> - **Riconoscimento istantaneo:** Specificare esplicitamente il protocollo `http://` garantisce che tutte le fotocamere e app scanner aprano direttamente il browser web invece di interpretare l'indirizzo come testo generico.

---

### 8. Spegnimento Programmato e Risparmio Energetico
Per salvaguardare la scheda SD da spegnimenti brutali dell'alimentazione e preservare lo schermo durante la notte:

1. Apri la tabella dei cronjob come amministratore:
   ```bash
   sudo crontab -e
   ```
2. Seleziona `nano` come editor (opzione 1) e aggiungi in fondo la riga per spegnere il sistema all'orario desiderato (es. ogni sera alle 19:30):
   ```bash
   30 19 * * * /sbin/poweroff
   ```
3. Salva con `CTRL+O` seguito da `Invio` ed esci con `CTRL+X`.

Alla mattina successiva, al ripristino dell'alimentazione (o tramite orologio programmabile / ciabatta oraria), il Raspberry Pi si riavvierà automaticamente avviando la dashboard.

*(Per board avanzate come Raspberry Pi 5 con batteria RTC è possibile configurare anche l'avvio temporizzato via hardware).*

---

### 9. Verifica e Collaudo Finale
Riavvia la scheda per verificare l'intera catena di avvio:
```bash
sudo reboot
```

Al riavvio, il sistema deve:
1. Eseguire l'autologin alla console.
2. Avviare Xorg e Openbox.
3. Lanciare `server_api.py` in background.
4. Aprire Chromium a tutto schermo in modalità Kiosk puntando alla dashboard.

Per qualsiasi anomalia o diagnostica rapida, consulta la sezione **Troubleshooting** nel [README principale](README.md#🔧-troubleshooting-e-manutenzione-v2).
