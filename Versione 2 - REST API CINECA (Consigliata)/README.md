# Kiosk4Uplanner - Versione 2: REST API CINECA (Consigliata)

[⬅ Torna alla pagina principale](../README.md)

> 🚀 **Devi installare o configurare il Raspberry Pi da zero?**  
> 👉 **[Vai alla Guida di Installazione Passo-Passo (INSTALL.md)](INSTALL.md)**

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
* **Supporto Nativo HTTPS / SSL (Nuovo in v5.0):** Server Python a doppio canale in grado di servire in parallelo HTTP (8080) e HTTPS (8443) nello stesso processo, con fallback automatico e redirect configurabile.
* **Hub Preferenze e Gestione Multi-Schermo (Nuovo in v5.0):** Icona universale a ingranaggio (`⚙`) per aprire il pannello preferenze. Le locandine sono attive di default sul totem fisico e sugli schermi Digital Signage secondari (`?kiosk=1`), ma disattivate di default per gli utenti web remoti.
* **Ticker Notizie e Locandine:** Integrazione nativa di un feed scorrevole orizzontale o verticale per mostrare notizie (estraibili da fino a 6 fonti RSS o endpoint REST) e un carosello di locandine pubblicitarie, interamente gestibili dal pannello.
* **Layout Unificato e Responsive:** Un solo file `remoto.html` renderizza la dashboard per il monitor 40" dell'atrio (Fullscreen), per i PC degli uffici (Doppia colonna) e si adatta in modo nativo su Smartphone e Tablet comprimendosi a colonna singola.
* **Menu Fluttuante a Scomparsa (Info Badge):** Un menu rapido e interattivo integrato nella UI che espone link utili e documentazione di contatto.
* **Immunità agli Aggiornamenti:** Eventuali modifiche grafiche, banner istituzionali o manutenzioni dell'interfaccia Angular di U-Planner non romperanno mai la dashboard, poiché i dati viaggiano esclusivamente su un protocollo dati (JSON) che resta invariato.
* **Mapping Dinamico Edifici:** Grazie alla DEBUG_MODE, il sistema può auto-mappare tutti gli edifici disponibili con un semplice riavvio, eliminando la necessità di cercare manualmente gli ID nel DB di CINECA.
* **Gestione Avanzata degli Stati (P e C):** Distingue nativamente gli eventi Pubblicati (P) dai Confermati (C) tramite indicatori visivi e permette di nascondere gli eventi non definitivi.
* **Risoluzione Indisponibilità:** Identifica e mostra la causale reale per cui un'aula è indisponibile, evitando le vecchie diciture generiche (es. "Attività programmata").
* **Gestione Annullamenti e Modifiche Live:** Gli eventi "Annullati" (A) dal gestionale vengono intercettati automaticamente; il sistema traccia inoltre i cambiamenti in tempo reale (spostamenti di aula/orario) e li rende persistenti sul disco.
* **Layout CSS a "Compressione Automatica":** Il frontend (remoto.html) utilizza Flexbox per garantire che tutte le card siano sempre visibili senza bisogno di scroll, comprimendosi dinamicamente in base al numero di lezioni.

### 🏗️ Architettura del Sistema

Il progetto si compone di elementi fondamentali:
1. **`server_api.py` (Il Motore):** Server HTTP/HTTPS Python. Si autentica in automatico su CINECA, interroga gli impegni del giorno, mappa i dati, scarica i feed RSS/REST e serve l'interfaccia sulle porte configurate (`8080` HTTP, `8443` HTTPS).
2. **`remoto.html` (La UI):** Unica Web App in Dark Mode. Mantiene l'orologio, riproduce le locandine e disegna le aule attingendo ai dati del server. Riceve istruzioni per ricaricarsi in tempo reale ("Hot-Reload").
3. **`admin.html` (Il Pannello Admin):** Interfaccia riservata per gestire la configurazione e salvarla su disco.
4. **`~/.xinitrc` (L'Avvio Kiosk):** Script standard di Linux che si occupa di lanciare il server Python in background, aprire l'ambiente grafico e lanciare Chromium a tutto schermo in modalità Kiosk all'accensione del dispositivo.

```text
Workflow di Avvio del Sistema

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

---

### 🛠️ Installazione e Configurazione

Tutti i passaggi operativi per installare il software su Raspberry Pi OS Lite, configurare le dipendenze, abilitare l'autostart grafico a tutto schermo, recuperare le credenziali CINECA e configurare la rete sono descritti passo-passo nella guida dedicata:

👉 **[Apri la Guida all'Installazione Passo-Passo (INSTALL.md)](INSTALL.md)**

La guida operativa è strutturata in 9 fasi pratiche:
1. **Requisiti e Dipendenze:** Installazione pacchetti di sistema (`apt`).
2. **Copia e Posizionamento:** Albero cartelle e permessi script.
3. **Autostart e Modalità Kiosk:** Configurazione di `~/.bashrc` e `~/.xinitrc`.
4. **Configurazione Credenziali CINECA:** Configurazione via web `/admin` o YAML con procedura F12 per i parametri.
5. **Personalizzazione Iniziale:** Primo avvio e gestione dal pannello.
6. **Rete e Porte Standard (80 e 443):** Comandi unificati `iptables` per evitare la porta nell'URL.
7. **Configurazione HTTPS / SSL:** Certificati OpenSSL, server dual-thread e fail-safe.
8. **Spegnimento Programmato:** Cronjob o moduli RTC per salvaguardare l'hardware.
9. **Verifica e Collaudo Finale:** Checklist di primo avvio.

---

### 🖥️ Schermi Secondari e Digital Signage (`?kiosk=1`)

A partire dalla versione 5.0 è stata introdotta una gestione intelligente e dinamica del carosello delle locandine pubblicitarie/informative:

1. **Monitor Fisico del Totem (`localhost` / `127.0.0.1`):**
   - Le locandine sono **attive per impostazione predefinita**.
2. **Utenti da PC o Smartphone (Rete locale / Uffici):**
   - Le locandine sono **disattivate per impostazione predefinita**, permettendo a studenti e personale di consultare immediatamente l'orario delle aule senza interruzioni a tutto schermo.
   - Ogni utente può comunque attivarle a piacimento cliccando sull'icona a ingranaggio (`⚙`) in basso a destra: la preferenza verrà memorizzata nel `localStorage` del dispositivo.
3. **Schermi Secondari, Smart TV e Totem Extra (`?kiosk=1`):**
   - Se desideri collegare al server un monitor secondario, una Smart TV da corridoio o un player multimediale privo di tastiera, è sufficiente impostare l'URL includendo il parametro `?kiosk=1`:
     ```text
     http://[IP_DEL_RASPBERRY]:8080/?kiosk=1
     # oppure in HTTPS:
     https://[IP_DEL_RASPBERRY]:8443/?kiosk=1
     ```
   - Con questo parametro, il dispositivo viene immediatamente riconosciuto come postazione Kiosk: le locandine risulteranno attive di default senza richiedere alcuna interazione manuale sul browser o telecomando.

---

### 💾 Gestione Stato e Persistenza
Il sistema genera automaticamente il file `stato_impegni.json` nella cartella di progetto.
* **Reset manuale:** Se desideri "pulire" la memoria di tutti gli annullamenti o spostamenti salvati, basta eliminare il file con questo comando: 
  `rm /home/vincenzo/dashboard_aule/stato_impegni.json`
* **Log:** Il file `kiosk.log` è lo strumento principale per il monitoraggio e il debug. Per la guida completa a tutti i messaggi operativi, codici di errore e diagnostica di entrambi i file (`kiosk.log` e `server_api_sys.log`), consulta la 👉 **[Guida e Legenda dei Log (LEGENDA_LOG.md)](LEGENDA_LOG.md)**. 

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

---