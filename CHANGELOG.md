# Registro delle Modifiche (Changelog) - Kiosk4UPlanner

[⬅ Torna al README principale](README.md)

Tutte le modifiche degne di nota apportate al progetto **Kiosk4UPlanner** sono documentate in ordine cronologico inverso (dalla release più recente alla prima versione).
Il formato si basa sulle linee guida di *Keep a Changelog* e adotta un versionamento semantico e incrementale per rami di sviluppo.

---

<a id="indice-versioni"></a>
## 📑 Indice Riepilogativo delle Versioni

| Versione | Ramo / Branch | Data | Focus & Sintesi Architetturale | Dettagli |
| :---: | :--- | :---: | :--- | :---: |
| **[v5.3](#v53---disaccoppiamento-del-core-modularizzazione--csp-hardening)** | `refactor/core-decoupling-5.3` | Nov 2026 | **Disaccoppiamento del Core, Modularizzazione & CSP Hardening:** 6 interventi (`v5.3.6` ➔ `v5.3.1`: pacchetto `core/`, backoff esponenziale `N-05`, `NewsEngine` in RAM, `BuildingContext` con `fsync` fuori lock `ST-09` e reset atomico `ST-11.1`, semaforo 40 slot `ST-08`, login atomico `ST-10.3`, whitelist `N-10`, asset in `static/` + CSP `SEC-06`, sonda paginazione CINECA, auto-discovery `Debug Mode` e restyling `/admin`). | [Vai ➔](#v53---disaccoppiamento-del-core-modularizzazione--csp-hardening) |
| **[v5.2](#v52---frontend-media-hd-news-hub-ux--kiosk-lockdown)** | `feature/frontend-5.2` | Nov 2026 | **Frontend, Media HD, News Hub UX & Kiosk Lockdown:** 10 interventi (`v5.2.10` ➔ `v5.2.1`: upload binario, nomi immutabili, `ordine.json` atomico, cache `immutable`, Canvas 2160px WebP, Kiosk Lockdown + duty-cycle 10–50%, `/stato` + badge freschezza CINECA, timeout 5s news, semaforo diagnostico, `escapeHTML()` anti-XSS, ricerca News Hub, miniature/lightbox, percorsi `./` e `config.example.yaml`). | [Vai ➔](#v52---frontend-media-hd-news-hub-ux--kiosk-lockdown) |
| **[v5.1](#v51---backend-hardening--security-stability)** | `fix/backend-5.1` | Ott 2026 | **Backend Hardening & Security Stability:** 13 interventi (`v5.1.12` ➔ `v5.1.1`: motore annullamenti su 2 cicli + auto-healing + sentinella 500, rendering DOM selettivo anti-flicker, reset 04:00 fuso Roma, scrittura atomica/condizionale SHA-256, rate-limiter login, log rotativo 50 MB, Copy-on-Write su `CONFIG`, PNG/WEBP anti-traversal, hardening HTTP OWASP, parser RSS universale). | [Vai ➔](#v51---backend-hardening--security-stability) |
| **[v5.0 - FINAL](#v50---final---produzione-live-https-nativo-multi-monitor-admin-accordion)** | `main` | Ott 2026 | **[Prima Produzione Live] & HTTPS Nativo:** Server multi-thread dual-stack HTTP/HTTPS, filtro anti-bot socket, bypass totem locale, `/admin` a schede e accordion, Hub preferenze responsive, `?kiosk=1`, `LEGENDA_LOG.md` e `INSTALL.md`. | [Vai ➔](#v50---final---produzione-live-https-nativo-multi-monitor-admin-accordion) |
| **[v4.7](#v47---guida-porta-http-80-integrazione-rete-e-sicurezza-avvio-kiosk)** | `main` | Ott 2026 | **Porta Standard (80) & Allineamento:** Guida porta 80 (`iptables`, `setcap`, `nginx`) e promemoria sincronizzazione porta con `~/.xinitrc`. | [Vai ➔](#v47---guida-porta-http-80-integrazione-rete-e-sicurezza-avvio-kiosk) |
| **[v4.6](#v46---news-hub-interattivo-multi-fonti-e-fix-backend)** | `main` | Ott 2026 | **News Hub Interattivo & Multi-Fonti:** Modale notizie ordinabile, fino a 6 fonti RSS/REST con pesi 1–5, compatibilità WordPress/Drupal e preferenze in `localStorage`. | [Vai ➔](#v46---news-hub-interattivo-multi-fonti-e-fix-backend) |
| **[v4.5](#v45---parametri-dinamici-ui-fixing-e-scrolling-invisibile)** | `main` | Ott 2026 | **Parametri Dinamici & UI Polish:** Anno Accademico e Contesto dinamici da `/admin`, limite 500 eventi, scrollbar invisibile e fix layout mobile. | [Vai ➔](#v45---parametri-dinamici-ui-fixing-e-scrolling-invisibile) |
| **[v4.0](#v40---gestione-remota-hot-reload-e-footer-informativo)** | `main` | Ott 2026 | **Pannello Web Admin & Hot-Reload:** Configurazione centralizzata in `config.yaml`, interfaccia `/admin`, aggiornamenti a caldo senza riavvio e footer news. | [Vai ➔](#v40---gestione-remota-hot-reload-e-footer-informativo) |
| **[v3.5](#v35---gestione-avanzata-eventi-uplanner)** | `main` | Ott 2026 | **Stati U-Planner Avanzati:** Distinzione Pubblicati (P) e Confermati (C), filtro visibilità, flag automatico Annullati (A) e causali reali di indisponibilità aula. | [Vai ➔](#v35---gestione-avanzata-eventi-uplanner) |
| **[v3.0](#v30---responsive-design-ux-improvements--logic-fixes)** | `main` | Giu 2026 | **Responsive Design & Drawer:** Layout CSS Grid/Flexbox mobile, pulizia cache a mezzanotte e cassetto informativo dinamico. | [Vai ➔](#v30---responsive-design-ux-improvements--logic-fixes) |
| **[v2.0](#v20---architettura-client-server--integrazione-api-ufficiale)** | `main` | Giu 2026 | **Nascita Versione 2 (REST API):** Demone Python `server_api.py`, autenticazione CINECA nativa, persistenza `stato_impegni.json` e tracciamento spostamenti. | [Vai ➔](#v20---architettura-client-server--integrazione-api-ufficiale) |
| **[v1.0](#v10---initial-release-scraping-dom---legacy)** | `legacy` | Giu 2026 | **Release Iniziale (Legacy):** Visualizzazione totem basata su *DOM Injection* dal calendario pubblico via Chromium. | [Vai ➔](#v10---initial-release-scraping-dom---legacy) |

---

<a id="v53---disaccoppiamento-del-core-modularizzazione--csp-hardening"></a>
## [v5.3] - Disaccoppiamento del Core, Modularizzazione & CSP Hardening
*Ramo di sviluppo:* `refactor/core-decoupling-5.3`  
*Data:* Novembre 2026  
*Stato:* Completato  

Questa milestone porta a compimento 6 interventi strutturali per il disaccoppiamento architetturale del backend nel pacchetto `dashboard_aule/core/`, la separazione degli asset frontend in `dashboard_aule/static/` (**Opzione 1 `D-19`**, propedeutica alla separazione `app/` vs `data/` della Milestone `v5.4`), l'attivazione della `Content-Security-Policy` rigorosa anti-XSS, l'hardening di concorrenza e rete del server HTTP e la messa in sicurezza completa dell'integrazione con CINECA U-Planner (salvaguardia obbligatoria su Anno Accademico e Contesto e auto-discovery estesa in `Debug Mode`).

Con la release `v5.3` vengono chiusi integralmente i 7 rilievi architetturali e di sicurezza pianificati nel Risk Assessment (**`N-05`**, **`ST-09`**, **`ST-11.1`**, **`ST-08`**, **`ST-10.3`**, **`N-10`**, **`SEC-06`**), oltre alla verifica sul campo della paginazione CINECA (**`ST-05` / `D-17`**):

---

### 🔹 v5.3.6: Sonda paginazione CINECA, salvaguardia obbligatoria Anno/Contesto, auto-discovery in `Debug Mode` e restyling `/admin`
* **Commit:** `540bbde`
* **Come era prima:** Non era noto se l'endpoint RPC `POST /Impegni/getImpegniCalendario` di CINECA U-Planner rispettasse parametri di paginazione (`skip`, `offset`, `page`) oltre il tetto di 500 eventi (`ST-05` / `D-17`). Lasciando vuoti `anno_accademico_id` o `contesto_id`, l'utente rischiava risposte vuote o troncate a 500 impegni, e per reperire gli ID esadecimali di 24 caratteri era necessario ispezionare manualmente il traffico di rete del browser con `F12`.
* **Come è ora:**
  - **Sonda paginazione (`verifica_supporto_paginazione`) e salvaguardia obbligatoria:** all'avvio autenticato, `CinecaClient` verifica se `skip`/`offset`/`page` producono pagine disgiunte (abilitando in tal caso il recupero multipagina fino a `MAX_PAGINE_CINECA = 10`). Poiché l'istanza CINECA UP di Ateneo ignora tali parametri, entra automaticamente in funzione la **salvaguardia obbligatoria** (`valida_configurazione_salvaguardia`): con credenziali CINECA attive e fuori dalla modalità debug, `/api/admin/save` richiede obbligatoriamente `anno_accademico_id` e `contesto_id` validati tramite regex di sicurezza `RE_ID_CINECA_SICURO` (4–64 caratteri alfanumerici, con blocco lato client/`HTTP 400` lato server e richiesta di conferma se diversi dai 24 caratteri esadecimali tipici).
  - **Auto-Discovery estesa in `Debug Mode` (`scopri_anagrafiche_debug`):** attivando il `Debug Mode`, il demone interroga `/AnniAccademici` e `/Contesti` e stampa in chiaro in `kiosk.log` le mappe complete di **Anni Accademici** (con marcatori automatici `[ANNO IN CORSO]` e `[IN USO]`) e **Contesti** (Poli didattici, Dipartimenti, Aree), oltre alla mappa **Edifici**, consentendo il salvataggio temporaneo senza Anno/Contesto durante la prima configurazione.
  - **Restyling e guide contestuali in `/admin` e `config.example.yaml`:** aggiunto nella tendina CINECA un box guida sul filtro a due stadi (*Anno Accademico + Contesto → Edificio*), spostata la spunta *Abilita Debug Mode* direttamente dentro *Credenziali e Connessione CINECA*, applicato un bordino sinistro colorato distintivo a tutte le 7 tendine ad accordion, documentato il funzionamento dell'interleaving del `peso` (1–5) delle fonti news e arricchiti `config.example.yaml` / `DEFAULT_CONFIG` con commenti completi ed esempio pronto all'uso di fonte RSS.
* **Perché questa modifica:** Previene strutturalmente qualsiasi perdita silenziosa di lezioni oltre il limite dei 500 impegni di U-Planner, rende immediata la prima configurazione e il cambio annuale di Anno Accademico anche senza usare gli strumenti sviluppatore `F12`, e migliora la chiarezza operativa del pannello `/admin`.

---

### 🔹 v5.3.5: Estrazione asset JS/CSS in `static/`, rimozione codice inline e attivazione CSP (`SEC-06`, `D-19`)
* **Commit:** `2873a9f` *(include il consolidamento UI di `f61aea1`)*
* **Come era prima:** `remoto.html` e `admin.html` incorporavano migliaia di righe di `<script>` e `<style>` inline oltre ad attributi `onclick`/`onchange` e `style="..."` dinamici. Questa struttura impediva l'attivazione di una `Content-Security-Policy` efficace senza bloccare il funzionamento della dashboard (**rilievo `SEC-06`**). Inoltre alcune chiamate in `admin` usavano ancora percorsi assoluti con `/` iniziale.
* **Come è ora:**
  - **Disaccoppiamento frontend secondo `D-19` (Opzione 1):** estratti integralmente JavaScript e CSS nella nuova sottocartella `dashboard_aule/static/` (`static/remoto.js`, `static/remoto.css`, `static/admin.js`, `static/admin.css`), lasciando `remoto.html` e `admin.html` come puro markup semantico privo di qualsiasi `<script>`, `<style>`, handler `on*=` o attributo `style=` inline (sostituiti da `addEventListener`, classi CSS e proprietà CSSOM).
  - Esposte in `server_api.py` le route dedicate `/static/remoto.js` e `/static/remoto.css` (pubbliche) e `/static/admin.js` e `/static/admin.css` (protette da `_check_security()`), migrando tutte le `fetch()` e gli URL locandine di `static/admin.js` al prefisso relativo `./`. Preservato inoltre il riordino UX della scheda *Personalizzazione* con la tendina *Interfaccia Dashboard & Digital Signage* posizionata in cima (`f61aea1`).
  - **Attivazione Content Security Policy (`SEC-06`):** iniettato su tutte le risposte HTTP l'header rigoroso `Content-Security-Policy: default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self'; frame-ancestors 'self'`.
* **Perché questa modifica:** Neutralizza alla radice l'esecuzione di script iniettati o risorse esterne non autorizzate completando la difesa in profondità anti-XSS (**chiusura `SEC-06` / `D-09`**), mantiene pulita la radice di `dashboard_aule/` e prepara la transizione verso il layout `app/` vs `data/` della Milestone `v5.4`.

---

### 🔹 v5.3.4: Refactoring `server_api.py`, semaforo concorrenza (`ST-08`), login atomico (`ST-10.3`) e whitelist `/api/admin/save` (`N-10`)
* **Commit:** `416e43f`
* **Come era prima:** `ThreadingHTTPServer` accettava un numero illimitato di thread concorrenti senza timeout sui socket TCP client, esponendo il Raspberry Pi a rischi di esaurimento memoria o attacchi di tipo Slowloris (**rilievo `ST-08`**). L'endpoint `/api/admin/login` verificava e aggiornava `LOGIN_ATTEMPTS` in due fasi distinte soggette a race condition TOCTOU sotto raffiche parallele (**rilievo `ST-10.3`**). Infine, `/api/admin/save` applicava `.update()` diretto dei dizionari JSON ricevuti senza filtrare le chiavi ammesse (**rilievo `N-10`**).
* **Come è ora:**
  - `server_api.py` è stato rifattorizzato in un router HTTP/HTTPS snello che delega a `BuildingContext`, `CinecaClient` e `NewsEngine`.
  - **Timeout socket e semaforo di concorrenza (`ST-08`):** impostato `timeout = 15.0` secondi su `KioskServer` e introdotto `threading.BoundedSemaphore(40)`. Al superamento dei 40 slot simultanei, il server risponde immediatamente con `HTTP 503 Service Unavailable` + `Retry-After: 5` e *lingering close* TCP (RFC 7230 §6.6), rilasciando sempre lo slot nel blocco `finally`.
  - **Rate-limiter login atomico (`ST-10.3`):** la funzione `verifica_login_admin()` esegue pulizia record scaduti, verifica lockout, confronto della password a tempo costante (`hmac.compare_digest`) e incremento del contatore sotto un **unico lock atomico** `lock_login` (5 tentativi max → blocco IP per 10 minuti con `HTTP 429` e `Retry-After`), eseguendo il delay difensivo di 1s fuori dal lock.
  - **Validazione a whitelist rigorosa (`N-10`):** introdotte `CONFIG_WHITELIST`, `FONTI_WHITELIST` e `valida_payload_admin_save()` su `POST /api/admin/save`, che rifiutano con `HTTP 400` qualsiasi sezione o chiave non autorizzata, impediscono la modifica via API di `percorso_base` e bloccano path traversal o nomi file non sicuri su `file_log`, `file_certificato` e `file_chiave`.
* **Perché questa modifica:** Protegge il Raspberry Pi da saturazione di thread e socket appesi (**chiusura `ST-08`**), rende matematicamente inaggirabile il blocco anti-brute force anche con richieste simultanee (**chiusura `ST-10.3`**) e impedisce attacchi di *mass assignment* sulla configurazione (**chiusura `N-10`**).

---

### 🔹 v5.3.3: Incapsulamento stato in `core/building_context.py`, `fsync` fuori lock (`ST-09`) e reset atomico (`ST-11.1`)
* **Commit:** `3b43cf3`
* **Come era prima:** Lo stato operativo dell'edificio (`storico_impegni`, `memoria_dati`, reset delle 04:00 AM e pipeline locandine) era distribuito su variabili globali in `server_api.py`. Durante `salva_stato()`, la sincronizzazione fisica su MicroSD (`os.fsync()`) veniva eseguita trattenendo lo stesso lock usato dai lettori HTTP di `/dati.json` (**rilievo `ST-09`**). Inoltre, il file `ultimo_reset.txt` veniva sovrascritto direttamente senza file temporaneo (**rilievo `ST-11.1`**), rischiando il troncamento a 0 byte in caso di blackout alle 04:00 del mattino.
* **Come è ora:**
  - Creata la classe `BuildingContext` in `core/building_context.py` che incapsula lo stato di runtime, la configurazione e l'intera pipeline locandine (`ordine.json`, magic bytes e guardia anti path-traversal) di un singolo edificio.
  - **Scorporo gerarchico dei lock (`lock_disco` → `lock_memoria`, chiusura `ST-09`):** `salva_stato()` acquisisce `lock_memoria` per meno di 1 ms solo per serializzare lo snapshot JSON in RAM, lo rilascia immediatamente ed esegue tutte le operazioni su MicroSD (`.tmp` + `flush` + `os.fsync` + `os.replace`) sotto il solo `lock_disco`, lasciando le letture concorrenti di `/dati.json` sempre istantanee.
  - **Persistenza atomica del reset giornaliero (`ST-11.1`):** `registra_reset_atomico()` scrive `ultimo_reset.txt` tramite file temporaneo univoco per PID/thread, `flush()`, `os.fsync()` e `os.replace()` atomico, validando il formato `YYYY-MM-DD` alla lettura.
* **Perché questa modifica:** Elimina qualsiasi micro-latenza HTTP durante le scritture su schede MicroSD lente (**chiusura `ST-09`**), blinda il marcatore del reset mattutino contro le interruzioni di corrente (**chiusura `ST-11.1`**) e prepara nativamente l'architettura multi-tenant della futura Campus Edition.

---

### 🔹 v5.3.2: Estrazione `core/news_engine.py`, confinamento totale in RAM e semaforo diagnostico
* **Commit:** `019d1c6`
* **Come era prima:** Le funzioni di scaricamento RSS/Atom/REST, normalizzazione delle date, interleaving pesato e diagnostica delle fonti erano intrecciate con le variabili globali di `server_api.py`, rendendo complessa l'evoluzione verso istanze multiple e la verifica formale dell'assenza di scritture su disco.
* **Come è ora:**
  - Estratto il modulo autonomo thread-safe `core/news_engine.py` (`NewsEngine`), con **confinamento rigoroso al 100% in RAM** della coda notizie e della mappa diagnostica (**zero chiamate `open()` o I/O su MicroSD**).
  - Consolidati nel motore il timeout invalicabile di **5 secondi** per singola fonte, il parsing XML/Atom da buffer binario nativo (`res.content`), la sanitizzazione HTML multilinea (`re.DOTALL`), la normalizzazione date in `DD/MM/YYYY`, l'interleaving deterministico pesato (`1–5`) e la classificazione semaforica (`🟢` OK, `🔴` Timeout / HTTP / XML-JSON error, `⚪` Disabilitata).
  - Mantenuta in `server_api.py` un'interfaccia delegante completamente retrocompatibile.
* **Perché questa modifica:** Isola il sottosistema delle notizie in un componente puro e riutilizzabile, azzera l'usura della scheda MicroSD del Raspberry Pi durante il polling dei feed e garantisce che una fonte esterna lenta o corrotta non degradi mai le altre.

---

### 🔹 v5.3.1: Estrazione `core/cineca_client.py`, backoff esponenziale (`N-05`) e timeout 15s
* **Commit:** `ba48903`
* **Come era prima:** Tutta la logica di autenticazione, interrogazione REST e riconciliazione degli annullamenti CINECA risiedeva monoliticamente in `server_api.py`. In caso di credenziali errate, scadenza account o prolungata indisponibilità dell'Identity Provider di Ateneo, il demone ripeteva tentativi di login ogni 120 secondi all'infinito (**rilievo `N-05`**), esponendo l'utenza tecnica al rischio di blocco automatico lato server remoto.
* **Come è ora:**
  - Creato il pacchetto backend `dashboard_aule/core/` e il modulo autonomo `core/cineca_client.py` (`CinecaClient`), privo di dipendenze dal server HTTP, con trasferimento integrale del motore annullamenti a conferma d'assenza (`D-01`) e della sentinella `LIMITE_EVENTI_CINECA = 500`.
  - Implementato il **backoff esponenziale con jitter controllato (`N-05`)** sui tentativi di login falliti (`120s → 240s → 480s → 960s → 1920s → max 3600s` / da 2 a 60 minuti): durante la finestra di blocco non viene aperta alcuna connessione HTTP verso CINECA, mentre il primo login o sync riuscito (`HTTP 200`) azzera istantaneamente i contatori.
  - Impostato un timeout esplicito di **15 secondi** su tutte le chiamate HTTP verso U-Planner.
* **Perché questa modifica:** Rende il client CINECA riutilizzabile in ottica multi-edificio, protegge l'account istituzionale da blocchi per tentativi ripetuti durante i disservizi di rete (**chiusura `N-05`**) e impedisce che socket appesi blocchino il thread di aggiornamento.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v52---frontend-media-hd-news-hub-ux--kiosk-lockdown"></a>
## [v5.2] - Frontend, Media HD, News Hub UX & Kiosk Lockdown
*Ramo di sviluppo:* `feature/frontend-5.2`  
*Data:* Novembre 2026  
*Stato:* Completato  

Questa milestone porta a compimento 10 interventi mirati a trasformare la dashboard e il carosello multimediale in un sistema Digital Signage professionale ad alta affidabilità per Raspberry Pi, blindato da manomissioni (Kiosk Lockdown), arricchito con indicatori di freschezza orari in tempo reale, diagnostica integrata delle fonti news e hardening OWASP contro vulnerabilità XSS.

Tutti gli interventi sono stati sviluppati e collaudati tramite mini-commit atomici corredati da 123 unit test automatici:

---

### 🔹 v5.2.10: Percorsi relativi `./`, `config.example.yaml`, file runtime esclusi da git, guardia `url_base` e security alert potenziato
* **Commit:** `7075b58`
* **Come era prima:** Le chiamate `fetch()` in `remoto.html` utilizzavano percorsi assoluti con slash iniziale (es. `/dati.json`), impedendo il funzionamento del totem se erogato dietro reverse proxy o sotto-cartelle URL. `config.yaml` e `kiosk.log` erano tracciati in git con rischio di sovrascritture di configurazioni locali. Il cambio di `url_base` CINECA da `/admin` non richiedeva la password di ateneo, rischiando disallineamenti di autenticazione. L'alert per la password predefinita in `/admin` non era sufficientemente esplicativo.
* **Come è ora:** Tutti gli endpoint e gli asset di fallback in `remoto.html` e `server_api.py` sono convertiti in percorsi relativi (`./config_pubblica`, `./dati.json`, `./api/news`, `./lista_locandine.json`, `./stato`, `./logo.png`, `./locandine/...`). Creato il file modello documentato `config.example.yaml`; `config.yaml` e `kiosk.log` rimossi dall'indice git e protetti in `.gitignore`. Aggiunta guardia su `/api/admin/save`: modificando `url_base` viene richiesta la re-immissione esplicita della password CINECA. Il riquadro Digital Signage documenta i vantaggi di `?kiosk=1`. Spostati toggle e badge locandine nella sezione dedicata. Potenziato il banner `#security-banner` con avviso `SECURITY ALERT: Password predefinita in uso ("cambiami")` e link per impostare nuova password e subnet IP autorizzati.
* **Perché questa modifica:** Garantisce massima portabilità della dashboard su qualsiasi architettura di rete (root o subpath), protegge le configurazioni di produzione, salvaguarda l'autenticazione CINECA e rafforza la sicurezza d'accesso al totem.

---

### 🔹 v5.2.9: Miniature lazy e lightbox con metadati per le locandine, escapeHTML in `admin.html`
* **Commit:** `1db2f31`
* **Come era prima:** Nella gestione locandine di `/admin`, la lista mostrava solo testo o immagini caricate a piena risoluzione che rallentavano l'interfaccia. Non era possibile visualizzare un'anteprima ingrandita né conoscere le dimensioni effettive su disco dei file senza accedere da SSH.
* **Come è ora:** Introdotte miniature proporzionali con caricamento pigro (`loading="lazy"`, `max-height: 70px`, `max-width: 120px`). Facendo clic su una miniatura si apre una finestra Lightbox ad alta risoluzione con metadati completi: nome file, dimensioni, peso in KB e data/ora di caricamento. Esteso l'uso di `escapeHTML()` a tutte le renderizzazioni dinamiche in `admin.html`.
* **Perché questa modifica:** Rende la gestione delle locandine visuale, rapida e intuitiva anche in presenza di molti contenuti promozionali memorizzati.

---

### 🔹 v5.2.8: Sanitizzazione `escapeHTML()` centralizzata, ricerca nel News Hub, switch slider e `Referrer-Policy`
* **Commit:** `a38fa7f`
* **Come era prima:** Alcune interpolazioni di stringhe nel DOM (come titoli di notizie o descrizioni) potevano teoricamente prestarsi a XSS in presenza di feed malevoli. Il modale News Hub conteneva una tabella statica senza filtro di ricerca. I comandi di abilitazione fonti erano normali checkbox HTML.
* **Come è ora:** Creata la funzione centralizzata `escapeHTML()` e applicata su tutte le interpolazioni dinamiche del DOM in `remoto.html`. Nel News Hub è stata introdotta la ricerca full-text in tempo reale con debounce a 150ms per filtrare gli articoli per titolo, fonte o data. Le checkbox delle fonti in `admin.html` sono state convertite in moderni interruttori a scorrimento (slider switch toggle). Rinforzato l'header di sicurezza HTTP `Referrer-Policy: no-referrer`.
* **Perché questa modifica:** Completa l'hardening difensivo OWASP contro vulnerabilità XSS, protegge la privacy degli accessi esterni e migliora l'usabilità della consultazione notizie da smartphone e PC.

---

### 🔹 v5.2.7: Semaforo diagnostico per fonte news con conteggio articoli e codice errore
* **Commit:** `95f8513`
* **Come era prima:** Nel pannello `/admin`, l'amministratore visualizzava solo l'elenco delle fonti configurate senza alcun indizio sull'effettivo funzionamento degli URL, sullo stato di raggiungibilità del server remoto o su eventuali feed rotti da tempo.
* **Come è ora:** L'endpoint `/api/news` arricchisce ciascuna fonte con metadati diagnostici (`stato_fetch`, `http_code`, `articoli_validi`, `errore_dettaglio`, `ultimo_fetch_ts`). In `admin.html`, ogni fonte mostra un semaforo diagnostico visivo in tempo reale: 🟢 **Verde** (attivo e funzionante, con conteggio articoli estratti), 🔴 **Rosso** (errore con tooltip esplicativo: Timeout, HTTP 404, Parse Error), ⚪ **Grigio** (fonte disattivata).
* **Perché questa modifica:** Consente all'amministratore di individuare all'istante problemi di connettività o URL errati dei feed RSS direttamente dal pannello web, senza consultare i log sul terminale.

---

### 🔹 v5.2.6: Timeout 5s per fonte news, pesi validati 1-5, parsing RSS da byte nativi e modularità news
* **Commit:** `37a6d27`
* **Come era prima:** Se un feed RSS esterno andava in blocco o rispondeva con forte latenza, l'intero demone delle notizie rimaneva appeso per minuti. I pesi delle fonti accettavano valori arbitrari senza controllo. Il parsing XML su stringhe decodificate provocava errori di mojibake (`UnicodeDecodeError` o lettere accentate corrotte) sui feed con encoding ISO-8859-1 dichiarati nell'header XML.
* **Come è ora:** Ciascuna fonte RSS/Atom ha un timeout invalicabile di 5 secondi (`timeout=5`). I pesi sono confinati rigorosamente tra 1 e 5. Il parsing XML opera direttamente sul buffer binario (`ET.fromstring(res.content)`), consentendo al parser XML di interpretare correttamente la codifica nativa (UTF-8, ISO-8859-1, Windows-1252). La logica delle news è stata inoltre estratta in funzioni helper dedicate e coperte da test unitari.
* **Perché questa modifica:** Rende l'acquisizione delle notizie deterministica e rapida, impedisce blocchi di I/O ed elimina le anomalie tipografiche sui caratteri speciali.

---

### 🔹 v5.2.5: Badge di freschezza CINECA via `/stato`, classificazione orari in RAM e tabellone mai cancellato
* **Commit:** `b4f0670`
* **Come era prima:** Il frontend considerava la connessione attiva se il server locale rispondeva, anche se CINECA era irraggiungibile da ore. Inoltre, dopo 4 errori consecutivi di fetch verso il server locale, il frontend cancellava completamente la schermata delle lezioni sostituendola con un messaggio di errore. Infine, la transizione di una lezione tra "Prossimi" e "In Corso" avveniva solo ogni 5 minuti al polling del server.
* **Come è ora:**
  - Introdotto l'endpoint `/stato` che espone lo stato effettivo della sincronizzazione con CINECA. Il badge di freschezza sulla dashboard mostra l'orario reale dell'ultimo aggiornamento d'ateneo con semaforo dinamico (🟢 < 10m, 🟡 10-30m, 🔴 > 30m o errore).
  - Eliminata la cancellazione distruttiva del tabellone: in caso di disconnessione o riavvii, gli ultimi orari validi rimangono sempre consultabili a video, accompagnati da una notifica discreta di allerta.
  - Introdotta la funzione `classificaImpegni()` lato client in `remoto.html`: a ogni ciclo di rendering (15s), il browser ricalcola in memoria l'inizio e la fine degli eventi rispetto all'orologio di sistema, promuovendo le lezioni a "In Corso" al secondo esatto senza attendere il polling del server.
* **Perché questa modifica:** Assicura massima trasparenza sull'aggiornamento dei dati, previene schermate vuote sul totem in caso di cali di rete e garantisce sincronizzazione al minuto spaccato per l'inizio delle lezioni.

---

### 🔹 v5.2.4: Lock-down kiosk, chiusura al tocco/ESC e carosello a catena con duty-cycle configurabile 10-50%
* **Commit:** `ee83e3a`
* **Come era prima:** In modalità totem (`?kiosk=1`), gli utenti potevano toccare lo schermo e cliccare sui link esterni delle notizie o del meteo, uscendo dalla dashboard a tutto schermo. Le locandine giravano con un rigido `setInterval` che poteva sovrapporsi agli orari nei momenti meno opportuni, e non era possibile chiudere una locandina a video prima dello scadere del timer.
* **Come è ora:**
  - In modalità `?kiosk=1`, tutti i collegamenti ipertestuali esterni sono disabilitati (`pointer-events: none`). Un watchdog di inattività a 60 secondi richiude automaticamente qualsiasi modale rimasto aperto.
  - Al tocco sullo schermo, clic del mouse o pressione di `ESC`, qualsiasi locandina aperta si chiude istantaneamente, tornando subito alla visualizzazione orari.
  - Il carosello locandine adotta una catena asincrona di `setTimeout` sequenziali governata da un duty-cycle configurabile da pannello Admin (10% - 50%, predefinito 20%), che garantisce matematicamente che il tabellone orari rimanga visibile per la maggior parte del tempo (dal 50% al 90% del tempo totale).
* **Perché questa modifica:** Trasforma il Kiosk in un dispositivo pubblico anti-vandalismo, garantendo che gli orari didattici abbiano sempre la precedenza assoluta sui contenuti promozionali.

---

### 🔹 v5.2.3: Cache browser immutabile, ridimensionamento client Canvas (max 2160px) e feedback toast
* **Commit:** `f6f021d`
* **Come era prima:** `remoto.html` utilizzava parametri di cache-busting (`?t=Date.now()`) a ogni ciclo del carosello, costringendo il totem a riscaricare continuamente immagini da diversi megabyte, saturando la banda e provocando micro-lag. In admin, immagini fotografiche pesanti caricate da smartphone venivano trasferite grezze al server.
* **Come è ora:** Grazie ai nomi immutabili, il server eroga le locandine con cache permanente (`Cache-Control: public, max-age=31536000, immutable`), e `remoto.html` ha rimosso qualsiasi parametro anti-cache. In `admin.html`, un canvas HTML5 esegue il downscaling automatico lato client preservando le proporzioni (lato lungo max 2160px / 4K) e comprime in WebP (qualità 0.88, con fallback JPEG), riducendo il peso del file del 70-90% prima del trasferimento. Introdotto inoltre un sistema di toast visivi non bloccanti.
* **Perché questa modifica:** Azzera il traffico di rete sul totem durante il carosello dopo il primo scaricamento, elimina i lag di render e riduce drasticamente l'occupazione di memoria e storage del Raspberry Pi.

---

### 🔹 v5.2.2: Ordine logico con `ordine.json` atomico e cancellazione singola senza rinomine fisiche
* **Commit:** `9fd6fea`
* **Come era prima:** La sequenza delle locandine era dettata dal prefisso numerico nel nome del file. Eliminare o spostare una locandina costringeva il backend a rinominare a catena tutti i file nella cartella `locandine/`, con rischio di corruzioni e conflitti I/O se un file era aperto in lettura dal browser.
* **Come è ora:** L'ordinamento è gestito a livello logico tramite `ordine.json`. L'endpoint `/api/admin/locandine/ordine` e la cancellazione singola `/api/admin/locandine/elimina` aggiornano la lista ordinata tramite scrittura atomica (`ordine.json.tmp` -> `os.replace`). La cancellazione rimuove solo il singolo file immutabile bersaglio, validando il percorso contro attacchi di directory traversal (`os.path.basename` e controllo directory canonica).
* **Perché questa modifica:** Elimina race conditions su disco, rende istantanee le operazioni di riordino ed eliminazione e assicura massima robustezza e scalabilità all'archivio multimediale.

---

### 🔹 v5.2.1: Upload binario grezzo, nomi immutabili `p<epoch>_<hex>`, Content-Length robusto e rotazione `server_api_sys.log`
* **Commit:** `ce4138a`
* **Come era prima:** L'upload delle locandine avveniva tramite stringhe Base64 (con overhead del +33% in memoria) o multipart complessi, e rinominava i file su disco ogni volta che l'ordine veniva modificato (`01_nome.jpg`). La lettura dello stream HTTP non gestiva in modo granulare i limiti e le interruzioni di rete. Lo script `.xinitrc` non controllava le dimensioni di `server_api_sys.log`, rischiando la saturazione del disco a lungo termine.
* **Come è ora:** Upload tramite streaming binario puro (`application/octet-stream`). I file su disco ricevono nomi immutabili basati su timestamp epoch e token casuale esadecimale (`p<epoch>_<hex>.<ext>`), slegando l'identità fisica del file dalla sequenza logica di visualizzazione. Lettura stream a chunk protetta da limite stringente (10 MB). In `~/.xinitrc` è stata introdotta la rotazione automatica con troncamento a 5 MB di `server_api_sys.log` prima dell'avvio del server.
* **Perché questa modifica:** Elimina l'overhead di RAM, azzera il rischio di immagini corrotte durante l'upload, isola il filesystem dalle riordinazioni logiche e garantisce che nessun log di sistema saturi la MicroSD del totem.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v51---backend-hardening--security-stability"></a>
## [v5.1] - Backend Hardening & Security Stability
*Ramo di sviluppo:* `fix/backend-5.1`  
*Data:* Ottobre 2026  
*Stato:* Completato  

Questa milestone introduce 13 interventi architetturali, di consolidamento e hotfix di produzione (10 mini-commit sequenziali + 1 fix scoping a HEAD + 1 consolidamento finale post-collaudo + 1 hotfix v5.1.12 CINECA auto-healing) mirati a elevare l'affidabilità, la sicurezza difensiva, la salvaguardia dell'hardware (MicroSD dei Raspberry Pi) e la fluidità visiva del Kiosk prima del passaggio alla release v5.2.

Ciascun intervento è stato sviluppato, testato e consolidato tramite mini-commit atomici:

---

### 🔹 v5.1.12: Motore annullamenti a conferma d'assenza, auto-healing, filtri non distruttivi e sentinella limite 500
* **Commit:** `1230679`
* **Come era prima:** Quando un evento non compariva nel feed CINECA per un singolo glitch o timeout di rete, veniva subito bollato come "ANNULLATO". Se l'evento riappariva al polling successivo, l'avviso di annullamento persisteva fino alle 04:00 del mattino successivo. Gli eventi filtrati dalla configurazione (aule escluse o stato C nascosto) venivano erroneamente trattati come annullati anziché rimossi silenziosamente. Mancava inoltre un allarme nel caso in cui gli eventi giornalieri toccassero il tetto massimo interrogabile (500).
* **Come è ora:**
  - **Conferma d'assenza su 2 cicli consecutivi (`SOGLIA_ASSENZE_ANNULLAMENTO = 2`):** Un impegno viene marcato come ANNULLATO solo se risulta assente per 2 interrogazioni consecutive (10 minuti), azzerando i falsi positivi da jitter di rete.
  - **Auto-Healing:** Se un evento precedentemente marcato ANNULLATO o SOSPESO ricompare regolarmente nel feed CINECA, il sistema ne ripristina all'istante lo stato regolare rimuovendo l'avviso.
  - **Filtri non distruttivi:** Gli eventi esclusi a monte dalle preferenze (edificio o stati non selezionati) vengono rimossi dalla memoria senza generare falsi allarmi di cancellazione.
  - **Sentinella LIMITE_EVENTI_CINECA:** Il demone verifica se il payload tocca i 500 eventi e genera un warning nei log (`⚠️ Raggiunto limite massimo eventi CINECA`) per sollecitare la riconfigurazione.
  - Creata la prima suite di unit test automatizzati (`tests/test_annullamenti.py` con 14 test) e corretta la dicitura in `admin.html` in *"Mostra ANCHE eventi Confermati (Stato C)"*.
* **Perché questa modifica:** Elimina qualsiasi falso allarme visivo per studenti e docenti, gestisce con intelligenza le fluttuazioni temporanee dei server di ateneo e introduce il framework di test automatizzati nel progetto.

---

### 🔹 v5.1.11: Consolidamento Post-Collaudo — Polish date RSS/Drupal, countdown live login, ordinamento news e log circuit-breaker
* **Commit:** *(Commit finale di consolidamento v5.1)*
* **Cosa include:**
  - **Normalizzazione Date RSS/Atom e Drupal (`DD/MM/YYYY`):** Risolta la mancata valorizzazione delle date estratte da feed XML con tag foglia (`item.find() is not None` invece di valutazione booleana) e introdotta la funzione `parse_data_notizia()` in grado di interpretare formati RFC-822, ISO 8601, date testuali con mesi in italiano (`23 Ottobre 2026`) e standard Drupal/WordPress, formattandole in modo omogeneo in `DD/MM/YYYY`.
  - **Countdown Dinamico Live nel Rate-Limiter Admin (`admin.html`):** L'endpoint `/api/admin/login` invia il campo `secondi_attesa` nel JSON di errore `HTTP 429`. L'interfaccia web mostra ora un timer decrescente in tempo reale (`🚨 Troppi tentativi falliti. Riprova tra X secondi.`) che scorre fino a zero e notifica visivamente all'utente il momento esatto in cui può reinserire la password.
  - **Ordinamento Cronologico nel News Hub (`remoto.html`):** La colonna "Data ↕" del modale notizie ordina ora gli articoli per timestamp effettivo anziché per stringa alfabetica, garantendo un ordinamento cronologico perfetto.
  - **Affinamento Log Diagnostico Circuit-Breaker (`server_api.py`):** Distinto chiaramente il messaggio di log in caso di attivazione del salvavita CINECA (`🛡️ Nessun nuovo dato CINECA: X impegni precedenti mantenuti a video`), evitando la precedente dicitura potenzialmente fuorviante `Dati ricevuti`.
* **Perché questa modifica:** Conclude il collaudo sul campo in ambiente reale di produzione, rifinendo i dettagli emersi dai test operativi e portando la milestone v5.1 a uno stato di completa stabilità e maturità prima del merge sul ramo principale.

---

### 🔹 v5.1.7-fix: Scoping `global CONFIG` nel gestore HTTP POST in `server_api.py`
* **Commit:** `08998d7` *(11° commit a HEAD del ramo fix/backend-5.1)*
* **Come era prima:** All'interno del metodo `do_POST` in `server_api.py`, l'assegnazione e il salvataggio della configurazione aggiornata riassegnavano il puntatore senza la previa dichiarazione `global CONFIG`, scatenando un'eccezione runtime `UnboundLocalError: local variable 'CONFIG' referenced before assignment` su Python 3.11+.
* **Come è ora:** È stata inserita la dichiarazione esplicita `global CONFIG` all'inizio del gestore POST, garantendo che le riassegnazioni del dizionario di configurazione avvengano sul puntatore globale condiviso in memoria in modo trasparente e thread-safe.
* **Perché questa modifica:** Elimina l'errore di scoping variabile Python a runtime durante il salvataggio da `/admin`, assicurando il funzionamento ininterrotto e affidabile del backend.

---

### 🔹 v5.1.10: Compatibilità bi-direzionale RSS per WordPress e Drupal Views con sanitizzazione sicura
* **Commit:** `b4aa06d`
* **Come era prima:** Il parser RSS di `NewsPollingDaemon` assumeva una gerarchia rigida di elementi XML standard (`<item><title><link>`). Molti feed di ateneo generati da viste esportate di Drupal o da temi WordPress personalizzati contenevano tag HTML annidati, frammenti CDATA o link inseriti nei campi `guid`/`enclosure`, provocando la mancata estrazione del testo o il rendering grezzo di codice HTML nel ticker.
* **Come è ora:** Il modulo di parsing XML è stato riscritto con estrazione ricorsiva del testo puro da tutti i sotto-nodi (`itertext()`), fallback intelligente per il recupero dei permalink da nodi alternativi (`guid`, `enclosure`, tag con namespace) e un rigoroso filtro di sanitizzazione con regex che purifica il testo da tag HTML residui, entità malformate e caratteri non sicuri prima di inviarlo al frontend.
* **Perché questa modifica:** Assicura piena interoperabilità con qualsiasi feed RSS o Atom generato dai portali universitari (WordPress, Drupal, Joomla, CMS custom) e garantisce una resa tipografica impeccabile e sicura sul nastro scorrevole delle notizie.

---

### 🔹 v5.1.9: Hardening HTTP difensivo con limite 1 MB su POST, 10 MB su upload e header OWASP base
* **Commit:** `7e6b72e`
* **Come era prima:** Gli handler HTTP del server leggevano il payload del corpo richiesta (`rfile.read()`) senza verificare un limite massimo stringente sull'header `Content-Length`. Inoltre, le risposte HTTP non includevano gli header standard di sicurezza raccomandati da OWASP.
* **Come è ora:** È stato introdotto un controllo preventivo con rigetto immediato (`HTTP 413 Payload Too Large`):
  - Limite massimo di **1 MB** per tutte le richieste API JSON standard (`/api/admin/...`).
  - Limite massimo di **10 MB** riservato esclusivamente all'upload multipart delle locandine.
  - Vengono iniettati sistematicamente su tutte le risposte gli header di hardening: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN` e `Referrer-Policy: no-referrer`.
* **Perché questa modifica:** Protegge il server da esaurimento della RAM (OOM / Denial of Service) per upload sproporzionati e blinda l'interfaccia web contro attacchi di clickjacking e MIME-sniffing.

---

### 🔹 v5.1.8: Supporto multi-formato per locandine (JPG, PNG, WEBP) e protezione path traversal
* **Commit:** `1d6eabf`
* **Come era prima:** Il carosello locandine accettava unicamente immagini in formato JPEG con estensioni fisse `.jpg` o `.jpeg`. Inoltre, le funzioni di caricamento ed eliminazione non eseguivano una bonifica capillare sul percorso del file, esponendosi a potenziali rischi di manipolazione del path (`../`).
* **Come è ora:** È stato esteso il supporto nativo ai formati grafici moderni **`.jpg`**, **`.jpeg`**, **`.png`** e **`.webp`**, associando a ciascuno il rispettivo MIME-type corretto nelle risposte HTTP. I nomi dei file caricati vengono sanitizzati rigorosamente e viene verificato che il percorso assoluto canonico (`os.path.realpath`) risieda rigidamente all'interno della cartella autorizzata `locandine/`.
* **Perché questa modifica:** Consente agli organizzatori degli eventi di caricare poster in alta qualità con trasparenza (PNG) o con compressione avanzata (WEBP), blindando il server contro qualsiasi vulnerabilità di directory traversal.

---

### 🔹 v5.1.7: Thread safety e pattern Copy-on-Write su `CONFIG` per salvataggi concorrenti sicuri
* **Commit:** `3849360`
* **Come era prima:** Il dizionario globale `CONFIG` veniva letto contemporaneamente da molteplici thread daemon di `ThreadingHTTPServer` per servire le richieste web e veniva modificato direttamente *in-place* quando l'amministratore salvava le impostazioni da `/api/admin/save`. Questa situazione esponeva l'applicazione a race conditions e a crash con eccezione `RuntimeError: dictionary changed size during iteration`.
* **Come è ora:** È stato introdotto un lock dedicato `lock_config = threading.Lock()` e adottato il pattern architetturale **Copy-on-Write**:
  - Le modifiche provenienti dal pannello web operano su una copia profonda (`copy.deepcopy(CONFIG)`).
  - Al termine della validazione e del salvataggio su file `config.yaml`, il riferimento globale viene riassegnato atomicamente sotto lock.
  - I thread di lettura accedono a copie immutabili o snapshot sincronizzati.
* **Perché questa modifica:** Garantisce una perfetta thread-safety nell'ecosistema multi-thread, eliminando i crash casuali del processo in occasione dei salvataggi amministrativi concorrenti.

---

### 🔹 v5.1.6: Logging rotativo a 50 MB complessivi con `RotatingFileHandler`
* **Commit:** `603ed5c`
* **Come era prima:** I log del server (`kiosk.log` e `server_api_sys.log`) venivano aperti e arricchiti in modalità append cumulativa indefinita. Su installazioni attive 24/7 per mesi, la crescita esponenziale dei file di log poteva arrivare a saturare l'intero spazio disco della partizione di root su Raspberry Pi, provocando il freeze del sistema operativo.
* **Come è ora:** L'infrastruttura di tracciamento è stata migrata al gestore standard `logging.handlers.RotatingFileHandler`. Ciascun file di log è confinato a un tetto massimo di **10 MB**, con un limite di **5 file di backup storici** a rotazione (`kiosk.log.1`, `kiosk.log.2`, ecc.). L'ingombro massimo su disco è rigidamente vincolato a **50 MB totali** per canale di log.
* **Perché questa modifica:** Assicura una manutenzione a "zero touch" e la massima stabilità operativa a lungo termine, impedendo qualsiasi saturazione della memoria di massa del chiosco.

---

### 🔹 v5.1.5: Rate-limiter in-memory su `/api/admin/login` e delay protettivo anti-brute force
* **Commit:** `2f171f0`
* **Come era prima:** L'endpoint di autenticazione `/api/admin/login` accettava ed elaborava richieste POST consecutive senza alcun controllo di frequenza, consentendo a un client all'interno della rete di ateneo di sferrare attacchi automatizzati di forza bruta (brute-force o dizionario) ad alta velocità.
* **Come è ora:** È stato implementato un modulo di rate-limiting in-memory associato all'indirizzo IP del client:
  - Massimo **5 tentativi di login errati** consentiti in una finestra di 5 minuti per ciascun IP.
  - Al superamento della soglia, l'IP viene **bloccato per 15 minuti**, rispondendo con codice `HTTP 429 Too Many Requests`.
  - Su ogni credenziale errata viene inoltre inserito un ritardo artificiale progressivo di sicurezza non bloccante per gli altri thread concorrenti.
* **Perché questa modifica:** Neutralizza i tentativi di violazione automatizzata della password del pannello di controllo, garantendo al contempo che il server continui a servire la dashboard agli utenti legittimi senza degrado di prestazioni.

---

### 🔹 v5.1.4: Protezione contro i falsi annullamenti di massa su anomalie temporanee CINECA
* **Commit:** `28dc28b`
* **Come era prima:** Se durante un'interrogazione periodica verso i server CINECA la risposta API risultava vuota o parziale a causa di una disconnessione temporanea, di una finestra di manutenzione del DB di ateneo o di un errore 500/503 del server remoto, la logica di tracciamento interpretava l'assenza degli eventi come una cancellazione ufficiale, contrassegnando istantaneamente tutte le lezioni della giornata come **"ANNULLATO"**.
* **Come è ora:** È stato integrato un meccanismo di salvaguardia (*circuit-breaker* su anomalie di massa). Se la chiamata CINECA restituisce una lista vuota o una contrazione drastica e improvvisa degli eventi attivi rispetto alla memoria locale senza un esplicito stato di cancellazione, il sistema rifiuta di processare gli annullamenti, genera un log di allerta diagnostica (`⚠️ Rilevata potenziale anomalia CINECA`) e preserva intatto lo stato corrente fino al polling successivo.
* **Perché questa modifica:** Scongiura il panico tra studenti e personale universitario evitando che per un'anomalia di rete transitoria di pochi minuti l'intero palinsesto giornaliero appaia erroneamente cancellato a video.

---

### 🔹 v5.1.3: Scrittura condizionale e atomica per salvaguardia MicroSD e resilienza ai blackout
* **Commit:** `b17960b`
* **Come era prima:** La funzione `salva_stato()` scriveva il file `stato_impegni.json` su disco ad ogni singolo ciclo di polling (ogni 5 minuti), anche in caso di totale assenza di variazioni negli orari delle lezioni. La scrittura avveniva aprendo il file in modalità sovrascrittura diretta (`open(..., 'w')`), con il grave rischio di corruzione irreparabile del JSON (file troncato a 0 byte) qualora si verificasse un blackout o uno spegnimento forzato durante l'operazione di I/O.
* **Come è ora:** È stato implementato un doppio pattern di protezione:
  1. **Scrittura Condizionale:** Il nuovo stato serializzato viene confrontato con l'hash crittografico (SHA-256) dell'ultimo stato salvato su disco. Se i dati sono identici, l'operazione di scrittura viene completamente saltata (*zero operazioni di I/O su disco*).
  2. **Scrittura Atomica e Sincronizzata:** Se i dati sono cambiati, il salvataggio avviene prima su un file temporaneo (`stato_impegni.json.tmp`), con forzatura dei buffer del sistema operativo tramite `file.flush()` e `os.fsync()`, seguito dalla sostituzione atomica (`os.replace()`).
* **Perché questa modifica:** Riduce di oltre il 90% le operazioni di scrittura su supporto fisico, prolungando drasticamente la vita utile delle schede MicroSD dei Raspberry Pi ed eliminando alla radice il rischio di file di stato corrotti dopo cali di tensione o riavvii accidentali.

---

### 🔹 v5.1.2: Reset giornaliero orari alle 04:00 AM con fuso Roma e catch-up all'avvio
* **Commit:** `42b972d`
* **Come era prima:** La cancellazione dello storico degli eventi e della memoria del server avveniva a mezzanotte in punto (00:00:00). Nelle installazioni dove il Raspberry Pi veniva spento durante la notte (es. per risparmio energetico) e riacceso al mattino, o in presenza di eventi notturni a cavallo di data, il calcolo orario basato su UTC puro provocava sfasamenti orari (CET/CEST) e il rischio di mostrare ancora a video gli orari del giorno precedente.
* **Come è ora:** L'orario di azzeramento giornaliero è stato spostato alle **04:00 AM** ed è ancorato rigidamente al fuso orario italiano `Europe/Rome` (gestendo in automatico l'alternanza tra ora solare CET e ora legale CEST, con fallback resiliente se il pacchetto tzdata non è presente sul sistema). Inoltre, all'avvio del server (`inizializza_demone()`), viene eseguito un controllo "catch-up": se l'ultimo reset registrato risale al giorno precedente, viene forzata una purga immediata della cache prima di effettuare il primo polling verso CINECA.
* **Perché questa modifica:** Le 04:00 del mattino rappresentano il fisiologico punto di quiete dell'ateneo tra due giornate accademiche consecutive. Questo garantisce che al primo avvio mattutino il totem sia sempre sincronizzato con il fuso locale e privo di impegni obsoleti della giornata precedente.

---

### 🔹 v5.1.1: Fix sfarfallio e ottimizzazione rendering selettivo DOM in `remoto.html`
* **Commit:** `f48c2dc`
* **Come era prima:** A ogni ciclo di polling del frontend (ogni 15 secondi), la funzione `aggiornaDati()` azzerava l'intero contenuto delle colonne "In Corso" e "Prossimi Eventi" tramite `contenitore.innerHTML = ''`, ricreando da zero tutti i nodi HTML. Questo provocava un fastidioso micro-sfarfallio (flicker) percepibile a occhio nudo sui monitor e resettava la posizione di scorrimento verticale degli utenti che consultavano la pagina da browser desktop o smartphone.
* **Come è ora:** È stata introdotta la funzione `confrontaERenderizza(contenitore, nuoviEventi, tipoColonna)`. Il nuovo algoritmo confronta la firma serializzata (`JSON.stringify`) di ciascun evento con quella salvata nel dataset dell'elemento DOM esistente (`card.dataset.eventData`). Se i dati non sono cambiati, il nodo HTML viene mantenuto intatto senza innescare reflow o repaint del browser; vengono aggiornate solo le card con variazioni effettive, rimosse quelle non più presenti e inserite quelle nuove.
* **Perché questa modifica:** Elimina totalmente il flickering visivo sul digital signage, mantiene inalterata la posizione di scroll dell'utente durante gli aggiornamenti in background e abbatte il carico computazionale su CPU e GPU del client.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v50---final---produzione-live-https-nativo-multi-monitor-admin-accordion"></a>
## [v5.0 - FINAL] - Produzione Live, Sicurezza HTTPS Nativa, Multi Monitor Support, Hub Preferenze e Nuovo Pannello Admin
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  
*Stato:* Rilasciato  

Questa major release segna il completamento dello sviluppo e la prima versione ufficiale destinata alla messa in produzione live. Introduce il supporto crittografico nativo HTTPS a doppio canale, rinnova totalmente il pannello di amministrazione e l'hub preferenze, ottimizza il Digital Signage multi-schermo, potenzia l'architettura con il multi-threading concorrente e introduce la nuova documentazione modulare e diagnostica.

### 🔒 Rete, Sicurezza & Crittografia HTTPS Nativa
* **Server Multi-Thread & Dual-Stack (`ThreadingHTTPServer` / `KioskHTTPServer`):** Gestione contemporanea non bloccante di connessioni HTTP (`8080`) e connessioni crittografate HTTPS/SSL (`8443`) con thread daemon nello stesso processo Python. Elimina i colli di bottiglia e i blocchi I/O quando più client (totem, browser desktop, smartphone) interrogano contemporaneamente la dashboard.
* **Filtro Anti-Bot & Soppressione Disconnessioni Fisiologiche:** Gestione personalizzata degli errori socket (`handle_error`) per filtrare e sopprimere i traceback di disconnessioni premature (`ConnectionResetError`, `BrokenPipeError`, `ConnectionAbortedError`) provocate da bot scanner internet o chiusure anticipate dei browser mobili, mantenendo pulito `server_api_sys.log`.
* **Protezione Fail-Safe Anti-Blocco:** Se i certificati SSL (`cert.pem`, `key.pem`) non sono presenti su disco, il server inibisce automaticamente qualsiasi reindirizzamento forzato verso HTTPS e continua a servire la dashboard in chiaro su HTTP, prevenendo schermate di errore `ERR_CONNECTION_REFUSED` sul totem.
* **Bypass Intelligente per Totem Locale:** Le richieste provenienti da `localhost`, `127.0.0.1` e `::1` non vengono mai reindirizzate a HTTPS, garantendo massime prestazioni ed evitando avvisi di certificati autofirmati sul browser locale del totem.
* **Port Redirection Completa con `iptables` (80 & 443):** Documentata e testata la configurazione a 4 regole per mappare in modo trasparente la porta 80 su 8080 e la 443 su 8443, sia per client esterni in ingresso sulla LAN (`PREROUTING`), sia per processi locali a bordo del Raspberry Pi (`OUTPUT`).
* **Allineamento Porte & `~/.xinitrc`:** Introdotte protezioni e avvisi mirati sia nel codice che nella documentazione per prevenire disallineamenti di porta all'avvio del chiosco.

### 🎛️ Pannello di Amministrazione Web (`/admin`)
* **Architettura a Due Macro-Schede:** Interfaccia utente riprogettata e suddivisa in due sezioni logiche:
  - **🎨 Personalizzazione:** Sezione rapida per l'uso quotidiano (avvisi di emergenza, grafica, locandine, notizie).
  - **⚙️ Sistema e Rete:** Sezione protetta con badge visivo *"Area Tecnica"* per credenziali CINECA, porte di ascolto e certificati SSL.
* **Layout ad Accordion (Tendine Collassabili):** Tutte le sezioni sono racchiuse in tendine a fisarmonica, chiuse di default all'accesso per garantire una panoramica pulita e ordinata ("colpo d'occhio").
* **Badge Dinamici di Stato:** Ogni tendina mostra un indicatore colorato in tempo reale sullo stato della configurazione (*NON ATTIVO / ATTIVO*, *Locandine: ON*, *Configurato*, *Porta 8080*, *DISABILITATO*).
* **Comandi Espandi/Comprimi Contestuali:** Pulsanti rapidi per aprire o chiudere tutte le tendine della scheda attualmente attiva.
* **Avviso di Emergenza (Alert Giallo) in Primo Piano:** Posizionato in cima alla scheda Personalizzazione con campo dedicato e box di **anteprima grafica live in tempo reale**.
* **Banner Sicurezza Interattivo:** Il promemoria sulla password predefinita è ora cliccabile e dirotta automaticamente l'amministratore alla scheda Sistema aprendo la tendina di sicurezza.

### 🖥️ Dashboard, Frontend & Digital Signage (`remoto.html`)
* **Resilienza Frontend & Tolleranza Errori Transitori:** Eliminato il distruttivo `window.location.reload()` in caso di interruzione temporanea di connettività: il frontend ora tollera brevi latenze o riavvii del server senza cancellare la vista a video, recuperando automaticamente i dati. Introdotto timeout dedicato (`AbortController`) a 10s per scongiurare chiamate HTTP appese.
* **News Hub Modale Responsive & Scroll Ottimizzato:** Riprogettato completamente il layout del modale delle preferenze con struttura flex-body e contenitore a scorrimento indipendente (`.news-table-wrapper`). Su schermi compatti e smartphone il modale si adatta fluidamente fino all'85% dell'altezza schermo garantendo una consultazione agevole della tabella notizie.
* **Intestazioni Colonne Fisse (Sticky):** I titoli delle colonne "In Corso" e "Prossimi Eventi" rimangono sempre ancorati in alto sotto l'orologio e il logo, mentre le card delle lezioni scorrono verticalmente in modo fluido e indipendente.
* **Hub Preferenze e Icona Ingranaggio (⚙):** Sostituito il vecchio pulsante `+` nel footer con un'icona universale a ingranaggio (`⚙`), che apre il modale unificato per la gestione di notizie e visualizzazione.
* **Ottimizzazione Ticker Notizie su Mobile:** Introdotto text-clamping su due righe per la modalità verticale e centratura Flexbox dell'icona ingranaggio per scongiurare tagli visivi del testo sui display compatti degli smartphone. Aggiunto inoltre il conteggio numerico delle notizie disponibili per ciascuna fonte attiva nel modale.
* **Controllo Condizionale Locandine nel Modale:** Il comando di attivazione/disattivazione locandine per utenti web è disabilitato e oscurato con badge esplicativo qualora l'amministratore abbia disattivato globalmente il carosello.
* **Modalità Smart Multi-Schermo & Parametro `?kiosk=1`:**
  - **Totem Fisico e Smart TV (`?kiosk=1`):** Locandine attive per impostazione predefinita per l'uso come Digital Signage informativo.
  - **Utenti Web (PC / Smartphone):** Locandine disattivate di default per consultare immediatamente gli orari delle aule, con possibilità di salvarle nelle preferenze locali (`localStorage`).
* **Allineamento Script `.xinitrc`:** Aggiornato il comando di lancio di Chromium a bordo del Raspberry Pi per includere il parametro `?kiosk=1`.

### 🛠️ Motore Dati, Debug & Diagnostica (`server_api.py`)
* **Parser RSS Universale (WordPress & Drupal Views):** Estrazione del testo ricorsiva da tutti i sotto-elementi del tag `<title>` e fallback automatico sui link racchiusi per garantire piena interoperabilità sia con feed generati da WordPress che con viste esportate da Drupal Views.
* **Ripristino Mappatura Dinamica Edifici in Debug Mode:** Quando `debug_mode: true` è attivo, il motore ispeziona il payload CINECA e stampa nei log la mappa esaustiva con tutti i codici edificio e relative descrizioni rilevate (`🕵️ DEBUG MAPPA EDIFICI RILEVATI`), facilitando la configurazione iniziale anche se un edificio è già impostato.

### 📚 Documentazione & Architettura Modulare
* **Guida e Legenda Completa dei Log (`LEGENDA_LOG.md`):** Creato un manuale di riferimento completo che spiega la distinzione tra `kiosk.log` (applicativo/dashboard) e `server_api_sys.log` (stdout/stderr di sistema/systemd), con la legenda di tutti i prefissi, codici di errore, anatomia dei traceback Python e relative procedure di risoluzione.
* **Separazione dei File di Documentazione:**
  - **`README.md`:** Panoramica concettuale, architettura Self-Healing del token CINECA e sintesi delle novità.
  - **`INSTALL.md`:** Guida operativa passo-passo numerata dall'inizio alla fine (Fasi 1–9) per installazione da zero.
* **Guida Multi-Utente Linux:** Documentazione dettagliata su come configurare l'utente di autologin per installazioni con account multipli.
* **Best Practice QR Code e URL:** Linee guida per la stampa di materiale promozionale/cartaceo con protocollo `http://` per transizione automatica e trasparente a HTTPS senza dover ristampare i codici.
* **Autorilevamento `percorso_base`:** Pulizia della variabile in `config.yaml` e documentazione del fallback automatico al percorso di esecuzione dello script Python.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v47---guida-porta-http-80-integrazione-rete-e-sicurezza-avvio-kiosk"></a>
## [v4.7] - Guida Porta HTTP 80, Integrazione Rete e Sicurezza Avvio Kiosk
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  

Questa release semplifica l'accesso alla dashboard tramite porta standard (`80`) e previene disallineamenti di porta all'avvio del chiosco.
* **Guida Porta HTTP Standard (80):** Aggiunta sezione dedicata nel README della Versione 2 con tre metodologie (Port Redirection con `iptables`, Capability Linux `setcap`, e Reverse Proxy `nginx`) per accedere al totem via IP o DNS senza specificare la porta `:8080`.
* **Sincronizzazione Porta e `~/.xinitrc`:** Introdotto promemoria critico nella documentazione e nell'interfaccia di amministrazione web (`admin.html`) per ricordare di allineare l'URL del comando Chromium in `~/.xinitrc` ogni volta che viene modificata la porta server locale, prevenendo schermate di errore `ERR_CONNECTION_REFUSED` sul monitor fisico del Kiosk.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v46---news-hub-interattivo-multi-fonti-e-fix-backend"></a>
## [v4.6] - News Hub interattivo, Multi-Fonti e Fix Backend
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  

Questa release introduce un'esperienza di consultazione delle notizie profondamente migliorata e risolve alcune criticità di salvataggio.
* **News Hub Modale:** Aggiunto un pulsante flottante `+` (con restyling in formato "pillola" SVG) così da permettere a chi accede da browser di aprire una finestra interattiva dove consultare tutte le notizie scaricate in una comoda tabella ordinabile alfabeticamente e per data (con frecce dinamiche ▲ / ▼).
* **Fonti Espansive e Peso:** Il sistema supporta ora l'immissione di fino a 6 fonti distinte contemporaneamente tramite il file YAML o dal pannello Admin. È stato aggiunto il parametro `peso` (da 1 a 5) per far apparire più o meno frequentemente una specifica fonte all'interno del nastro scorrevole.
* **Compatibilità Feed RSS:** Aggiornamento della sintassi del parser RSS per garantire piena compatibilità sia con feed generati da WordPress che con viste esportate da Drupal Views.
* **Preferenze Locali (LocalStorage):** Gli utenti che accedono da PC o Smartphone possono disattivare alcune fonti news per la loro sessione locale. Le preferenze vengono salvate nel browser tramite LocalStorage senza impattare il totem pubblico, che continuerà a seguire le regole `visibile_di_default` dettate dall'amministratore.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v45---parametri-dinamici-ui-fixing-e-scrolling-invisibile"></a>
## [v4.5] - Parametri Dinamici, UI Fixing e Scrolling Invisibile
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  

Questa release rende l'applicazione completamente svincolata da parametri hardcoded, potenziando il limite di eventi caricati e raffinando il comportamento dell'interfaccia sia su schermi enormi che su smartphone.
* **Parametri CINECA 100% Dinamici:** I codici dell'Anno Accademico e del Contesto (Sede), in precedenza incorporati nel codice sorgente, sono stati estratti e resi dinamici per un utilizzo universale.
* **Aggiornamento Pannello Admin:** L'interfaccia di amministrazione Web (`/admin`) è stata arricchita con i nuovi campi dedicati per l'inserimento rapido di `Anno Accademico ID` e `Contesto ID`. 
* **Aumento Limite Eventi:** Il numero massimo di eventi interrogabili singolarmente dalle API CINECA è stato innalzato in sicurezza da 150 a 500, garantendo che nessun impegno sfugga alla visualizzazione durante le giornate eccezionalmente cariche.
* **Scrolling Invisibile e Fix Testi (Desktop):** Risolto il problema del "testo affettato" (in cui nomi di docenti lunghi venivano tagliati a metà dal layout in caso di colonna satura). È stato inoltre sbloccato lo scorrimento verticale naturale delle colonne tramite una scrollbar volutamente invisibile, perfetta per mantenere la pulizia visiva del digital signage.
* **Fix Allineamenti e Footer (Mobile):** Ottimizzati drasticamente i calcoli per schermi piccoli: corretto il fastidioso "salto" della pagina provocato dall'alternanza di notizie sul ticker, ri-allineato chirurgicamente il box degli avvisi e impedito che frasi lunghe allungassero a dismisura l'intero footer.
* **Titolo Agnostico:** Rimosso il suffisso accademico fisso dal tag `<title>` della pagina per completare il processo di universalità del progetto.
* **Guida Parametri Inclusa:** Aggiornata la documentazione con istruzioni chiare e passo-passo su come reperire in autonomia i codici di configurazione necessari ispezionando la console di CINECA Up.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v40---gestione-remota-hot-reload-e-footer-informativo"></a>
## [v4.0] - Gestione Remota, Hot-Reload e Footer Informativo
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  

Questa major release trasforma il Kiosk in uno strumento pienamente amministrabile da remoto.
* **Unificazioni variabili in un unico file config.yaml:** Tutte le personalizzazioni risiedono in un unico file `config.yaml`.
* **Pannello di Amministrazione Web:** Oltre alla scrittura manuale su config.yaml, è presente una nuova interfaccia grafica (`/admin`) per modificare colori, testi, velocità e loghi senza toccare una riga di codice (il pannello di base è disattivato, ma può essere attivato da `config.yaml` in un secondo).
* **Hot-Reload e Resilienza:** I Kiosk in rete si aggiornano automaticamente in tempo reale ("a caldo") non appena si salva la configurazione dal pannello, senza bisogno di riavvii. Migliorata anche la ripresa automatica dopo cali di rete. 
* **Footer News Avanzato:** Introdotto un feed scorrevole personalizzabile (orizzontale o verticale) capace di integrarsi con API REST e RSS esterni. Le notizie sono cliccabili (con collegamento all'articolo originale). 
* **Gestione Locandine Intelligente:** Il carosello pubblicitario può ora essere disabilitato selettivamente (solo per il proprio browser) tramite il comodo badge informazioni, senza influenzare i monitor Kiosk di ateneo.
* **Log Centralizzati:** I file di log del sistema (`kiosk.log` e `server_api_sys.log`) sono ora generati direttamente nella cartella base `dashboard_aule` per un rapido accesso e agevolare il troubleshooting.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v35---gestione-avanzata-eventi-uplanner"></a>
## [v3.5] - Gestione avanzata eventi UPlanner
*Ramo di sviluppo:* `main`  
*Data:* Ottobre 2026  

Questa release affina ulteriormente la gestione dei dati provenienti da U-Planner, introducendo un controllo più preciso sugli stati degli eventi e migliorando la chiarezza delle informazioni esposte sulla dashboard.
* **Gestione granulare degli Stati (P e C):** Il sistema ora distingue chiaramente gli eventi Pubblicati (P) da quelli Confermati (C). Appositi indicatori visivi (pallini) vengono mostrati accanto al nome dell'evento per identificarne lo stato; tali indicatori possono essere comodamente disattivati se non necessari.
* **Filtro Eventi Confermati:** È stata introdotta la possibilità di nascondere completamente dalla vista gli eventi in stato Confermato (C).
* **Annullamenti Automatici (A):** Gli eventi contrassegnati come Annullati (A) da U-Planner vengono ora rilevati nativamente e flaggati in automatico come tali sull'interfaccia.
* **Risoluzione delle Indisponibilità:** Le indisponibilità delle aule vengono processate in modo completo mostrando la loro causale reale, eliminando la precedente e anonima dicitura di "Attività programmata".

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v30---responsive-design-ux-improvements--logic-fixes"></a>
## [v3.0] - Responsive Design, UX Improvements & Logic Fixes
*Ramo di sviluppo:* `main`  
*Data:* Giugno 2026  

Questa versione introduce il pieno supporto ai dispositivi mobili, una revisione completa dell'interfaccia utente (UX) e importanti ottimizzazioni nella gestione dei dati lato server.
* **Piena compatibilità Mobile:** Ristrutturazione del layout con CSS Grid e Flexbox per adattarsi perfettamente agli schermi degli smartphone. Introdotto il blocco dello scorrimento orizzontale e l'adattamento dinamico delle colonne.
* **Smart Data Reset:** Ottimizzata la logica di pulizia della cache in `server_api.py`. Gli eventi annullati o terminati non persistono più per 24 ore dall'orario di fine, ma vengono rimossi automaticamente allo scoccare della mezzanotte, garantendo un file JSON sempre pulito all'inizio di ogni nuova giornata.
* **Documentazione migliorata:** Separate le istruzioni per le varie versioni in file Markdown navigabili.
* **Nuovo Cassetto Informativo Dinamico:** Inserito menu a scomparsa laterale che si adatta al dispositivo in uso. Su ambiente desktop è quasi invisibile in basso a destra e introduce tooltip personalizzati in puro CSS ad apparizione istantanea. Su smartphone e tablet, il cassetto si trasforma in un menu verticale espandibile ottimizzato per il touch, con animazioni fluide e rotazione dinamica dell'icona.
* **Grid Blowout Fix:** Risolto il problema che causava l'allargamento spropositato delle schede in presenza di testi troppo lunghi (`min-width: 0` e `minmax(0, 1fr)`).
* **Fix troncamento testi:** Garantito il corretto funzionamento dei puntini di sospensione (`text-overflow: ellipsis`) per titoli degli esami e nomi dei docenti eccessivamente lunghi.
* **Fix UI Desktop & Touch:** Risolto un bug visivo che causava l'impilamento verticale errato dei link su desktop e disattivato l'effetto hover nativo sui dispositivi touch che bloccava la corretta chiusura del menu a scomparsa.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

<a id="v20---architettura-client-server--integrazione-api-ufficiale"></a>
## [v2.0] - Architettura Client-Server & Integrazione API Ufficiale
*Ramo di sviluppo:* `main`  
*Data:* Giugno 2026  

Questa release ha segnato il passaggio da un approccio puramente frontend a un solido sistema ibrido, introducendo un backend dedicato per garantire maggiore stabilità, precisione e l'accesso a dati avanzati non disponibili pubblicamente.

### ✨ Nuova Architettura e Backend Python
* **Server Locale Dedicato (`server_api.py`):** Sviluppato un demone in Python che agisce simultaneamente da motore di recupero dati e da web server HTTP leggero. Ora gestisce l'erogazione della dashboard (`remoto.html`), dei dati puliti (`dati.json`) e delle risorse multimediali (`/locandine/`).
* **Integrazione API CINECA (Modalità Admin):** Superata la tecnica di "DOM Injection" in favore dell'interrogazione diretta e strutturata degli endpoint API ufficiali di U-Planner.
* **Gestione Autenticazione Automatica:** Implementato un sistema di login per la richiesta, gestione e rinnovo automatico dei token di sicurezza necessari a comunicare con i server CINECA.
* **Polling Ottimizzato:** Il backend interroga le API a intervalli regolari (es. ogni 5 minuti), filtrando a monte le richieste per scaricare esclusivamente il carico didattico della giornata e dell'edificio d'interesse, riducendo drasticamente il traffico di rete.

### 🧠 Gestione Dati e Tracciamento Avanzato
* **Persistenza dello Stato (`stato_impegni.json`):** Creata una logica di salvataggio locale che mantiene in memoria l'intero storico degli eventi. Questo garantisce che la dashboard possa ripristinare immediatamente le informazioni in caso di riavvio improvviso del chiosco.
* **Rilevamento Annullamenti:** Il sistema confronta le nuove risposte API con il database locale; se un evento non ancora concluso scompare dal feed di U-Planner, viene automaticamente "congelato" e segnalato sulla dashboard con un badge visibile di **"ANNULLATO"**.
* **Tracciamento Spostamenti:** Aggiunta una logica di *diffing* (confronto) che rileva se un evento ha subito modifiche di orario o di aula, generando dinamicamente un avviso testuale sulla card ("Spostato da...").
* **Normalizzazione per il Frontend:** Il server backend si fa carico di analizzare le risposte JSON complesse, calcolare i timestamp e servire alla dashboard un set di dati pulito, leggero e pronto per essere renderizzato senza ulteriori sforzi computazionali da parte del browser.

[⬆ Torna all'indice delle versioni](#indice-versioni)

---

### 🛑 SPARTIACQUE ARCHITETTURALE: CONGELAMENTO VERSIONE 1 (LEGACY) & ADOZIONE UNICA VERSIONE 2 (REST API)

> [!IMPORTANT]
> **Punto di Svolta nello Sviluppo del Progetto (Giugno 2026):**
> Con il rilascio della release `v1.0` si conclude e si **arresta definitivamente lo sviluppo della Versione 1 (Scraping DOM con Chromium)**, che viene congelata e preservata nel repository esclusivamente come riferimento storico e soluzione di fallback per ambienti privi di credenziali U-Planner.
>
> A partire dalla **Versione 2.0**, l'intero sviluppo attivo del progetto Kiosk4UPlanner adotta in modo **esclusivo e permanente l'architettura Client-Server basata sulle REST API CINECA native**. Questa scelta ha eliminato il gravoso overhead computazionale di Chromium headless per l'estrazione dei dati, introducendo un demone Python leggero, token crittografici auto-rigeneranti, persistenza dello stato, rilevamento automatico degli annullamenti e sicurezza avanzata.
>
> Tutte le release successive (`v2.0` ➔ `v3.0` ➔ `v4.0` ➔ `v5.0` ➔ `v5.1` ➔ `v6.0`) appartengono unicamente alla **Versione 2**.

---

<a id="v10---initial-release-scraping-dom---legacy"></a>
## [v1.0] - Initial Release (Scraping DOM - Legacy)
*Ramo di sviluppo:* `legacy`  
*Data:* Giugno 2026  

* Prima versione stabile della dashboard per i display Kiosk.
* **Motore Base:** Sistema di reperimento dati basato esclusivamente sul metodo di *DOM Injection* dal calendario pubblico.
* Struttura visiva a colonne rigide (in corso / prossimi eventi) ottimizzata nativamente per schermi di grandi dimensioni (landscape o verticali) senza necessità di scorrimento.

[⬆ Torna all'indice delle versioni](#indice-versioni)
