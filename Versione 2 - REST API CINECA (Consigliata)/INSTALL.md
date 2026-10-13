# Guida all'Installazione Passo-Passo (Versione 2 - REST API CINECA)

[⬅ Torna alla Presentazione della Versione 2](README.md) | [🏠 Torna alla Pagina Principale del Progetto](../README.md)

---

Questa guida operativa ti accompagna passo-passo nell'installazione, configurazione e messa in produzione del Kiosk informativo su **Raspberry Pi OS Lite** (o distribuzioni Linux Debian-based compatibili).

### 📑 Indice delle Fasi
1. [Requisiti e Dipendenze di Sistema](#1-requisiti-e-dipendenze-raspberry-pi-os-lite)
2. [Copia e Posizionamento dei File](#2-copia-e-posizionamento-dei-file)
3. [Autostart e Modalità Kiosk (.bashrc e .xinitrc)](#3-autostart-e-modalità-kiosk-bashrc-e-xinitrc)
4. [Configurazione Credenziali CINECA (con procedura F12)](#4-configurazione-credenziali-cineca)
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
    ├── config.yaml        <-- File di configurazione
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
   - Avviare il server Python `server_api.py` in background.
   - Avviare il gestore finestre leggero `openbox`.
   - Lanciare `chromium` a tutto schermo in modalità Kiosk con il parametro `?kiosk=1` (che attiva automaticamente le locandine sul totem).

> 📺 **Monitor Secondari, Smart TV e Digital Signage (`?kiosk=1`):**  
> Se colleghi alla dashboard altri schermi o Smart TV da corridoio (es. TV con browser integrato WebOS/Tizen, stick Android o PC remoti senza Raspberry Pi), assicurati di aprire l'URL aggiungendo il parametro **`?kiosk=1`** (es. `http://[IP_DEL_RASPBERRY]:8080/?kiosk=1` o `http://totem.unipv.it/?kiosk=1`).  
> In questo modo il dispositivo viene riconosciuto come postazione Kiosk e mostrerà a rotazione il carosello delle locandine a schermo intero (che per i normali utenti web da PC o smartphone è invece disattivato di default).

---

### 4. Configurazione Credenziali CINECA
Tutta la configurazione strutturale (credenziali CINECA comprese) risiede nel file `config.yaml`.

Puoi procedere in due modalità:
- **Tramite Pannello Web (Consigliato):** Apri `config.yaml` e imposta temporaneamente `admin_attivo: true`. Avvia il server (`python3 server_api.py`) e dal tuo PC collegati a `http://[IP_DEL_RASPBERRY]:8080/admin` per compilare comodamente tutti i campi da interfaccia grafica.
- **Tramite Modifica Manuale:** Apri `config.yaml` con un editor (`nano config.yaml`) e compila la prima sezione `api_cineca` (`username`, `password`, `realm`, `id_edificio`, `anno_accademico_id`, `contesto_id`).

#### 💡 Procedura per il Recupero dei Parametri CINECA (Strumenti Sviluppatore / F12)
I parametri identificativi di CINECA U-Planner (`realm`, `anno_accademico_id`, `contesto_id`) possono essere recuperati in pochi istanti analizzando il traffico di rete del browser durante l'uso del portale web U-Planner del tuo Ateneo:

* **Recupero `realm` (Cliente ID dell'Ateneo):**
  1. Apri la pagina di login del portale U-Planner del tuo Ateneo (es. `https://[ateneo].prod.up.cineca.it/`) sul tuo PC.
  2. Apri gli Strumenti per Sviluppatori premendo **F12** (o tasto destro -> *Ispeziona* -> scheda **Rete / Network**).
  3. Attiva il filtro **Fetch/XHR** per isolare le chiamate API.
  4. Effettua l'accesso inserendo le tue credenziali.
  5. Individua la richiesta di autenticazione (solitamente denominata `login?include=user` o `login`).
  6. Clicca sulla richiesta e apri la sottoscheda **Risposta (Response)**: copia il valore alfanumerico associato alla chiave `"clienteId"` (o `"realm"`), composto da 24 caratteri esadecimali (es. `5a6734b248e4aa0cdeaaf875`).  
     *(Metodo alternativo: in qualsiasi chiamata successiva verso le API CINECA, apri la scheda Intestazioni/Headers e copia il valore dell'header `X-Realm`).*

* **Recupero `anno_accademico_id` (ID Anno Accademico):**
  1. All'interno del portale U-Planner, accedi alla visualizzazione del calendario/pianificazione delle lezioni.
  2. Con la scheda **Rete (Network)** aperta (filtro **Fetch/XHR**), digita `getImpegniCalendario` nella casella di ricerca.
  3. Seleziona la chiamata POST `getImpegniCalendario` (se non compare, cambia giorno o vista nel calendario per forzarne una).
  4. Clicca sulla sottoscheda **Payload** (o *Carico utile / Richiesta*).
  5. Individua il parametro **`annoAccademicoId`** e copia la stringa esadecimale di 24 caratteri (es. `5e1553cac831d600172af6d0`).

* **Recupero `contesto_id` (ID Contesto / Dipartimento):**
  1. Nel portale U-Planner, seleziona la struttura didattica o dipartimento di competenza.
  2. Nella medesima chiamata POST `getImpegniCalendario` (nella scheda **Payload**), individua il parametro **`contestoId`** e copia la stringa di 24 caratteri (es. `5b97788424deec000e171a8f`).

* **Recupero `id_edificio`:**
  1. In `config.yaml` imposta `debug_mode: true` (oppure attivalo dalla scheda CINECA del Pannello Admin) e riavvia il server.
  2. Attendi un ciclo di aggiornamento completo (circa 1 minuto).
  3. Leggi il file di log eseguendo:
     ```bash
     cat /home/vincenzo/dashboard_aule/kiosk.log
     ```
  4. Individua la riga speciale `"🕵️ DEBUG MAPPA EDIFICI"` contenente tutti i codici numerici e i nomi dei palazzi del tuo Ateneo.
  5. Inserisci l'ID del tuo palazzo nel campo `id_edificio` e rimetti `debug_mode: false`.

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
5. Cliccando su **"Salva Configurazione"**, il server aggiorna il file su disco e invia un segnale di "Hot Reload" a tutti i Kiosk collegati, che si aggiorneranno all'istante senza bisogno di riavvii.

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
- **Dal Pannello `/admin`:** Vai nella scheda *Rete e Sicurezza*, attiva la spunta **"Abilita Server HTTPS"**, imposta la porta (predefinita `8443`) e salva.
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
