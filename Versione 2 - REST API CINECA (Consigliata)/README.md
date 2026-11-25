# Kiosk4UPlanner - Versione 2: REST API CINECA (Consigliata)

[⬅ Torna alla Pagina Principale](../README.md) | [🛠️ Guida di Installazione (INSTALL.md)](INSTALL.md) | [📋 Legenda dei Log (LEGENDA_LOG.md)](LEGENDA_LOG.md) | [📜 Changelog](../CHANGELOG.md)

> 🚀 **Devi installare, aggiornare o configurare il Raspberry Pi passo-passo?**  
> Apri la **[Guida di Installazione (INSTALL.md)](INSTALL.md)** per i requisiti di sistema, l'avvio automatico in modalità Kiosk (`.xinitrc`), il recupero dei codici CINECA (`Debug Mode` o `F12`), il port-forwarding `80`/`443` (`iptables`) e il server HTTPS.

---

## 🧠 Come funziona la comunicazione API con CINECA

Questa versione abbandona lo scraping DOM del calendario web pubblico (usato nella Versione 1): un demone Python locale interroga direttamente gli endpoint **REST API ufficiali** di U-Planner (CINECA) scambiando dati strutturati in formato JSON.

All'avvio il server effettua l'accesso su CINECA (endpoint `/Utenti/login`) inviando `username` e `password` dell'account fornito dall'Ateneo insieme al parametro `realm` / `clientId` (il codice identificativo di 24 caratteri esadecimali dell'Ateneo, chiamato `clienteId` su U-Planner). CINECA risponde con un **token di sessione** opaco (valido tipicamente 14 giorni), che Python conserva **esclusivamente in RAM** e allega alle richieste successive negli header `Authorization` e `X-Realm`.

Il ciclo operativo del backend si articola in quattro compiti:

- **Autenticazione e Self-Healing (`HTTP 401`):** all'accensione viene richiesto un token fresco; se durante l'esercizio il token scade o viene revocato anticipatamente da CINECA (`HTTP 401 - Unauthorized`), il server lo invalida, attende `2 s`, ripete il login in background e riprende il servizio senza interventi manuali. Se invece il login stesso fallisce (credenziali errate o disservizio temporaneo del portale di accesso d'Ateneo), scatta un **backoff esponenziale** (`2 min → 60 min` con jitter) per evitare che tentativi ripetuti facciano bloccare l'account.
- **Filtro Giornaliero a Due Stadi:** interroga `POST /Impegni/getImpegniCalendario` limitando la finestra temporale alle **24 ore della giornata corrente** (`Europe/Rome`) e circoscrivendo la richiesta ad **Anno Accademico** (`annoAccademicoId`) e **Contesto** (`contestoId`: Polo didattico, Dipartimento o Area aule), così da restare sotto il limite CINECA di **500 impegni per chiamata**. Dal risultato ricevuto filtra localmente le sole aule del palazzo configurato (`id_edificio`, opzionale: se lasciato vuoto mostra l'intero Contesto).
- **Persistenza Giornaliera Anti-Blackout:** salva lo storico della giornata nel file locale `stato_impegni.json` tramite scrittura atomica (`.tmp` + `os.replace`) e **condizionale** (*zero scritture* su MicroSD finché gli orari non variano), azzerandolo ogni notte alle **04:00 AM** (`Europe/Rome`, tracciato in `ultimo_reset.txt` con recupero automatico all'accensione mattutina).
- **Manutenzione Ordinaria Minima:** a regime il totem non richiede presidio quotidiano; l'unico adempimento periodico è l'**aggiornamento annuale di `anno_accademico_id`** all'inizio di ogni nuovo Anno Accademico (es. settembre).

---

## 🚀 Caratteristiche Principali

*(Per la cronologia completa di tutte le versioni consulta il **[Changelog generale](../CHANGELOG.md)**).*

- **Leggerezza e Continuità Visiva:** invece di caricare sul Raspberry Pi la pesante web-app Angular di U-Planner, Chromium renderizza un'interfaccia locale leggerissima *(introdotta in v2.0)* con aggiornamento selettivo del DOM anti-sfarfallio *(aggiunto in v5.1)*. Le lezioni passano nella colonna *"In Corso"* al secondo esatto tramite ricalcolo in RAM e un **badge di freschezza (`/stato`)** mostra l'orario dell'ultimo sync CINECA mantenendo sempre visibile l'ultimo tabellone valido anche se cade la rete (`🔴 OFFLINE`) *(aggiunti in v5.2)*.
- **Layout Responsive a Scorrimento Invisibile:** un'unica vista Dark Mode *(responsive mobile e cassetto info aggiunti in v3.0; file JS/CSS separati in `static/` in v5.3)* dispone le due colonne (*In Corso* e *Prossimi Eventi*) su griglia CSS con scorrimento verticale fluido a scrollbar invisibile senza mai comprimere o tagliare i testi *(aggiunto in v4.5)* e intestazioni colonne fisse *sticky* *(aggiunte in v5.0)*; sotto i `768px` (smartphone) passa automaticamente a colonna singola.
- **Stati U-Planner, Indisponibilità e Motore Annullamenti:** traccia **annullamenti e spostamenti di aula/orario** *(introdotti in v2.0)*, distingue gli impegni **Pubblicati (`P`)** dai **Confermati (`C`, nascondibili)** con indicatori `P`/`C` opzionali, rileva gli stati **Annullati (`A`)** ed espone la **causale reale delle indisponibilità aula** *(aggiunti in v3.5)*. Per azzerare i falsi allarmi su glitch di rete integra *circuit-breaker* su risposte vuote, gestione stato **Sospeso (`S`)**, conferma d'assenza su **2 cicli consecutivi** (~10 min) e **auto-healing** istantaneo se la lezione ricompare *(aggiunti in v5.1)*.
- **Pannello Web `/admin` e Hot-Reload:** configurazione centralizzata in `config.yaml` e interfaccia `/admin` con aggiornamento a caldo dei browser collegati *(introdotti in v4.0; parametri Anno/Contesto dinamici aggiunti in v4.5)*, organizzata in due macro-schede con tendine collassabili e **Avviso di Emergenza (Alert Giallo)** con anteprima live *(aggiunti in v5.0)*. Protetta da filtro IP CIDR (di fabbrica `127.0.0.1`), rate-limiter anti-brute force con countdown *(aggiunto in v5.1)*, guardia cambio `url_base` *(aggiunta in v5.2)*, login atomico, whitelist rigorosa e box guida CINECA *(aggiunti in v5.3; il riavvio del demone serve solo cambiando porte o SSL)*.
- **Ticker Multi-Fonte e News Hub Modale:** barra inferiore configurabile a scorrimento *orizzontale* o dissolvenza *verticale* ogni `6 s` *(introdotta in v4.0)*, alimentata da fino a **6 fonti** con pesi `1–5` e **News Hub** modale ordinabile con preferenze `localStorage` *(aggiunti in v4.6)*. Supporta feed RSS 2.0 / Atom / Drupal Views e REST JSON WordPress con normalizzazione date `DD/MM/YYYY` *(aggiunti in v5.0–v5.1)*, timeout `5 s` per fonte, **semaforo diagnostico** in `/admin` e **ricerca full-text** istantanea *(aggiunti in v5.2)*, con motore 100% in RAM a zero scritture su MicroSD *(aggiunto in v5.3)*.
- **Pipeline Locandine Ottimizzata:** supporto formati JPEG, PNG e WebP protetto contro *path-traversal* *(aggiunto in v5.1)*, caricamento binario da `/admin` (max `10 MB` con verifica *magic bytes*), ridimensionamento automatico lato client (Canvas max `2160px` WebP), anteprima Lightbox, riordino logico senza rinominare i file e cache browser permanente `immutable` *(aggiunti in v5.2)*.
- **Auto-Discovery Anagrafiche in `Debug Mode`:** una volta impostati `username`, `password` e `realm`, attivando temporaneamente `debug_mode` il demone elenca in `kiosk.log` i codici **Edificio** rilevati negli impegni della giornata *(aggiunto in v5.0)* e interroga `/AnniAccademici` e `/Contesti` stampando tutti gli ID dell'Ateneo *(aggiunto in v5.3)* — in alternativa alla procedura via browser `F12` (vedi **[Sezione 4 di INSTALL.md](INSTALL.md#4-configurazione-credenziali-cineca)** e **[LEGENDA_LOG.md](LEGENDA_LOG.md)**).
- **Server HTTP + HTTPS Parallelo:** erogazione simultanea su porta HTTP (`8080`) e porta HTTPS/TLS (`8443`) in thread dedicati dello stesso processo Python, con fail-safe automatico su HTTP se i certificati SSL mancano e bypass del redirect per il browser locale del totem *(aggiunto in v5.0)*, blindato da timeout socket `15 s`, semaforo a `40` slot e `Content-Security-Policy` anti-XSS *(aggiunti in v5.3)*.

---

## 🏗️ Architettura del Sistema

Il codice della Versione 2 separa i motori di dominio nel pacchetto `dashboard_aule/core/` e le risorse frontend nella cartella `dashboard_aule/static/`:

```text
Versione 2 - REST API CINECA (Consigliata)/
├── .xinitrc                        # Script avvio X11: rotazione xrandr, openbox, watchdog Python e Chromium Kiosk
├── README.md                       # Architettura e guida funzionale della Versione 2
├── INSTALL.md                      # Manuale di installazione passo-passo su Raspberry Pi OS Lite
├── LEGENDA_LOG.md                  # Guida alla lettura di kiosk.log e server_api_sys.log
└── dashboard_aule/
    ├── server_api.py               # Entry-point HTTP/HTTPS, ciclo di polling, semaforo 40 slot, login e CSP
    ├── core/                       # Motori backend disaccoppiati
    │   ├── __init__.py
    │   ├── cineca_client.py        # Autenticazione CINECA, backoff esponenziale, sonda paginazione e annullamenti
    │   ├── news_engine.py          # Motore feed RSS/Atom/Drupal e WordPress REST 100% in RAM (zero I/O su disco)
    │   └── building_context.py     # Stato edificio, lock memoria/disco separati (fsync fuori lock) e locandine
    ├── static/                     # Asset frontend serviti su rotte dedicate sotto Content-Security-Policy
    │   ├── remoto.js               # Logica client dashboard pubblica, carosello duty-cycle e News Hub
    │   ├── remoto.css              # Foglio di stile responsive Dark Mode e Kiosk Lockdown
    │   ├── admin.js                # Logica client pannello /admin, downscaling Canvas WebP e diagnostica
    │   └── admin.css               # Foglio di stile del pannello di amministrazione
    ├── remoto.html                 # Markup HTML puro della dashboard pubblica (zero script/stili/handler inline)
    ├── admin.html                  # Markup HTML puro del pannello di amministrazione (zero script/stili/handler inline)
    ├── logo.png                    # Logo istituzionale predefinito
    ├── config.example.yaml         # Modello di configurazione commentato (da copiare in config.yaml)
    └── locandine/                  # Cartella locandine (esempi 1.jpg–4.jpg; in produzione p<epoch>_<hex>.<ext> + ordine.json)
```

Le responsabilità sono ripartite in quattro livelli:

1. **`server_api.py` (Entry-Point, Polling e Router HTTP/HTTPS):**
   - Gestisce l'ascolto parallelo su IPv4 per HTTP (`8080`) e HTTPS (`8443`), i thread daemon di sincronizzazione e il salvataggio Copy-on-Write di `config.yaml` preservando i commenti.
   - Protegge il server con timeout socket di `15 s` e semaforo di concorrenza `BoundedSemaphore(40)` (rispondendo subito `HTTP 503` + `Retry-After: 5` oltre i 40 slot simultanei).
   - Applica su `/api/admin/login` un rate-limiter atomico (max 5 tentativi / blocco IP 10 min) con confronto dell'hash `SHA-256` a tempo costante (`hmac.compare_digest`), valida `/api/admin/save` tramite whitelist rigorosa delle chiavi ammesse e inietta su tutte le risposte gli header di sicurezza OWASP e la `Content-Security-Policy` (`default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self'; frame-ancestors 'self'`).
2. **`core/` (I Motori di Dominio):**
   - **`cineca_client.py` (`CinecaClient`):** gestisce login e sessione U-Planner (timeout `15 s`), backoff esponenziale sui login falliti (`120 s → 3600 s` con jitter), sonda diagnostica di paginazione con salvaguardia obbligatoria su `anno_accademico_id` e `contesto_id`, interrogazione di `/AnniAccademici` e `/Contesti` in `Debug Mode`, sentinella del tetto di `500` eventi e motore di riconciliazione annullamenti/spostamenti.
   - **`news_engine.py` (`NewsEngine`):** scarica i feed RSS 2.0 / Atom / Drupal Views e gli endpoint JSON WordPress REST con timeout di `5 s` per fonte, parsing XML da byte nativi (`res.content`, compatibile con codifiche `UTF-8`, `ISO-8859-1` e `Windows-1252`), sanitizzazione HTML multilinea, interleaving pesato (`1–5`) e semaforo diagnostico (`🟢` / `🔴` / `⚪`), operando **interamente in RAM con zero scritture su MicroSD**.
   - **`building_context.py` (`BuildingContext`):** incapsula lo stato dell'edificio, separa `lock_memoria` da `lock_disco` eseguendo `os.fsync()` **fuori** dal lock di lettura per mantenere `/dati.json` istantaneo anche su MicroSD lente, persiste atomicamente `stato_impegni.json` e `ultimo_reset.txt` (reset delle `04:00 AM`) e governa l'archivio locandine (`ordine.json`, controllo *magic bytes* e guardia anti *path-traversal*).
3. **`remoto.html`, `admin.html` e `static/`:**
   - Separazione netta tra struttura DOM (markup HTML semantico privo di blocchi `<script>`, `<style>`, attributi `style=` o handler `on*=`) e i 4 asset statici serviti su rotte esplicite (`/static/remoto.js` e `/static/remoto.css` pubbliche; `/static/admin.js` e `/static/admin.css` protette dai medesimi controlli IP/abilitazione di `/admin`) con percorsi relativi `./`, requisito fondamentale per la `Content-Security-Policy` anti-XSS.
4. **`.xinitrc` (Avvio Grafico X11 e Watchdog Kiosk):**
   - Disabilita screensaver e risparmio energetico (`xset`), applica l'orientamento del display tramite `xrandr` (`NOME_MONITOR` e `ROTAZIONE_MONITOR` configurabili in testa allo script per monitor orizzontali o totem verticali), nasconde il cursore inattivo (`unclutter`) e avvia `openbox-session`.
   - Lancia `server_api.py` in un ciclo watchdog `while true` con rotazione automatica di `server_api_sys.log` a `5 MB` e, dopo `5 s` di avvio, esegue Chromium in modalità `--kiosk --incognito` su `http://localhost:8080/remoto.html?kiosk=1` *(vedi lo schema completo nella **[Sezione 3 di INSTALL.md](INSTALL.md#3-autostart-e-modalità-kiosk-bashrc-e-xinitrc)**)*.

---

## 🖥️ Modalità di Installazione: Monitor a Parete, Totem Touchscreen e PC/Smartphone

La stessa interfaccia supporta nativamente **tre scenari reali di utilizzo** negli spazi universitari, adattando locandine, interazione touch e blocchi di sicurezza:

1. **Monitor Fisico Appeso / Smart TV da Corridoio (Solo visualizzazione passiva):**
   - Ideale per schermi montati in alto negli atri o nei corridoi, privi di tastiera e fuori dalla portata del pubblico (sia il monitor collegato direttamente al Raspberry Pi su `localhost`, sia eventuali Smart TV o mini-PC secondari collegati via rete).
   - Per i display secondari basta configurare il browser integrato aprendo l'indirizzo con il parametro **`?kiosk=1`**:
     ```text
     http://[IP_DEL_RASPBERRY]:8080/?kiosk=1
     https://[IP_DEL_RASPBERRY]:8443/?kiosk=1
     ```
   - Il carosello delle locandine informative parte **automaticamente attivo** (purché abilitato globalmente in `/admin`), alternandosi da solo al tabellone delle aule secondo la quota di *Duty-Cycle* impostata.
2. **Totem a Colonna Touchscreen nell'Atrio (Postazione Pubblica Interattiva):**
   - Il sistema è già pronto per essere installato su **totem touch a pavimento** (sia orizzontali sia verticali) a disposizione di studenti e docenti, usando lo stesso indirizzo Kiosk (`localhost` sul Raspberry del totem oppure `?kiosk=1`):
     - **Scomparsa istantanea delle locandine al tocco:** se uno studente si avvicina mentre è a schermo una locandina, basta **toccare qualsiasi punto del display** perché la locandina sparisca all'istante lasciando subito spazio agli orari delle lezioni;
     - **Consultazione interattiva degli orari e degli avvisi:** dal display touch è possibile scorrere con il dito le colonne delle lezioni e toccare l'ingranaggio (`⚙`) **in basso a sinistra** per aprire il **News Hub**, cercare tra gli avvisi o leggere i titoli delle fonti d'Ateneo;
     - **Kiosk Lockdown anti-manomissione:** tutti i link verso pagine esterne (articoli web, calendario pubblico, crediti nel cassetto in basso a destra) sono **bloccati (`pointer-events: none`)**, impedendo a chiunque di uscire dalla dashboard o usare il totem per navigare altrove;
     - **Auto-ripristino dopo `60 s` di inattività:** se un utente apre il News Hub o il cassetto informativo e poi si allontana, dopo `60 s` senza tocchi tutte le finestre si richiudono automaticamente riportando il totem sul tabellone orari (e il carosello resta sempre forzato attivo, senza che un passante possa disabilitarlo).
3. **PC d'Ufficio e Smartphone Personali (Consultazione da Remoto):**
   - Aprendo l'indirizzo normale **senza** `?kiosk=1`, il carosello locandine parte **disattivato di default** per mostrare immediatamente l'occupazione delle aule senza attese.
   - Tutti i collegamenti esterni agli articoli delle notizie e al calendario pubblico sono regolarmente cliccabili, e tramite l'icona a ingranaggio (`⚙`) **in basso a sinistra** nel footer (visibile quando il footer notizie è abilitato) ciascun utente può personalizzare fonti e locandine salvando la preferenza nel `localStorage` del proprio dispositivo.

### ⏱️ Duty-Cycle del Carosello e Rotazione a Staffetta

Per evitare che la proiezione di molte locandine nasconda troppo a lungo gli orari delle lezioni, il carosello applica una politica di **Duty-Cycle** con rotazione circolare *(introdotta in v5.2)*:

- **Quota Massima (Duty-Cycle `10%–50%`):** dallo slider in `/admin` → *Locandine* si imposta la percentuale massima di tempo riservata alle locandine (valore predefinito: **30%**, che lascia circa il **70%** del ciclo al tabellone aule).
- **Gruppi e Rotazione a Staffetta (*Round-Robin*):** ogni schermata (*gruppo*) mostra **2 locandine affiancate** sui display orizzontali oppure **1 singola locandina** sui totem verticali. Se le locandine caricate superano il tempo concesso in un singolo ciclo, il sistema mostra solo i gruppi consentiti dal budget e al giro successivo riparte esattamente dal gruppo seguente *(toccando lo schermo, facendo clic o premendo `Esc`, l'overlay si chiude subito e il ciclo successivo riprenderà dopo `pausaTraCaroselli`)*.
- **Calcolo dei Gruppi per Ciclo:** detti `pausa` l'intervallo di tabellone orari tra due caroselli (default `180 s`), `quota` la frazione scelta (default `0.30`), `esposizione` la durata di ogni schermata (default `10 s`, comprensiva di `1.5 s` di dissolvenza in ingresso) e `transizione` il tempo tecnico di chiusura verso il tabellone (`1.55 s`: `0.05 s` di preparazione DOM + `1.5 s` di fade-out CSS):

$$
\text{budget} = \text{pausa} \times \frac{\text{quota}}{1 - \text{quota}}, \qquad \text{gruppiPerCiclo} = \max\!\left(1,\, \left\lfloor \frac{\text{budget}}{\text{esposizione} + \text{transizione}} \right\rfloor\right)
$$

  *(Con i valori predefiniti: $\text{budget} \approx 77.1\text{ s}$, pari a **6 schermate per ciclo** — fino a **12 locandine** su schermo orizzontale o **6** su schermo verticale; il vincolo $\max(1, \dots)$ garantisce comunque almeno 1 schermata per ciclo anche con pause molto brevi).*

---

<a id="troubleshooting-e-manutenzione-v2"></a>
## 🔧 Persistenza, Log e Manutenzione

Tutti i file runtime generati in locale dentro `~/dashboard_aule/` (`config.yaml`, `stato_impegni.json`, `ultimo_reset.txt`, `locandine/ordine.json`, `kiosk.log` e `server_api_sys.log`) sono esclusi da Git per non essere sovrascritti durante gli aggiornamenti, e i file di stato/configurazione vengono salvati con scrittura atomica (`.tmp` + `os.replace`).

- **Verifica stato del demone:** per controllare se il processo Python è in esecuzione:
  ```bash
  pgrep -af server_api.py
  ```
- **Consultazione Log Applicativo e Log di Sistema:** `kiosk.log` registra l'attività ordinaria e il `Debug Mode` (rotazione `10 MB x 5`), mentre `server_api_sys.log` raccoglie eventuali errori critici di avvio o traceback Python non gestiti (rotazione a `5 MB`; in condizioni normali resta a `0 byte`). Per tutti i messaggi consulta **[LEGENDA_LOG.md](LEGENDA_LOG.md)**:
  ```bash
  tail -f ~/dashboard_aule/kiosk.log
  cat ~/dashboard_aule/server_api_sys.log
  ```
- **Fine riga Windows/Linux (`dos2unix`):** se hai copiato o modificato gli script da un PC Windows, converti i caratteri `CRLF` in `LF` sia su `~/.xinitrc` (fondamentale per Bash) sia sui file Python:
  ```bash
  dos2unix ~/.xinitrc ~/dashboard_aule/server_api.py ~/dashboard_aule/core/*.py
  ```
- **Reset manuale di annullamenti e spostamenti del giorno:** per azzerare subito sia su disco sia in RAM gli annullamenti/spostamenti memorizzati nella giornata corrente, rimuovi `stato_impegni.json` e termina il processo Python (se avviato tramite `~/.xinitrc`, il watchdog lo rilancerà automaticamente entro `2 s`; se invece lo avevi lanciato manualmente da SSH, riavvialo con `python3 ~/dashboard_aule/server_api.py`):
  ```bash
  rm -f ~/dashboard_aule/stato_impegni.json && pkill -f server_api.py
  ```

---

[⬆ Torna all'inizio](#kiosk4uplanner---versione-2-rest-api-cineca-consigliata) | [⬅ Torna alla Pagina Principale](../README.md) | [🛠️ Guida di Installazione](INSTALL.md) | [📋 Legenda dei Log](LEGENDA_LOG.md)
