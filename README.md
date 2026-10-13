# Kiosk4Uplanner - Dashboard Kiosk Informativa

*Sviluppato per l'Università di Pavia (UNIPV)*

**Versione:** 5.0 | **Autore:** [Vincenzo Oriti](https://oriti.net) ([vincenzo.oriti@unipv.it](mailto:vincenzo.oriti@unipv.it)) | **Progetto:** [GitHub](https://github.com/VOriti/Kiosk4UPlanner) | **Licenza:** [CC BY-NC-SA 4.0](LICENSE.txt) ([Testo completo](https://creativecommons.org/licenses/by-nc-sa/4.0/))

---

Questo progetto trasforma un Raspberry Pi in una postazione **Kiosk informativa**, da installare negli atri di un polo universitario per mostrare a studenti e docenti lo stato di occupazione delle aule in tempo reale.

Ha principalmente tre funzioni:
- mostra **l'occupazione in tempo reale delle aule** del palazzo;
- ogni tot minuti **mostra eventuali locandine di eventi in corso o futuri**;
- **rende disponibili i dati su una pagina web all'interno della rete locale**. In questo modo, il personale può controllare l'occupazione corrente delle aule direttamente dal browser del proprio PC o Smartphone.

Il repository è diviso in **due versioni** indipendenti, per adattarsi ai livelli di accesso a disposizione della struttura:

* 📖 [**Versione 1: Scraping DOM (Senza API)**](Versione%201%20-%20Scraping%20DOM%20(Senza%20API)/README.md) - Soluzione fai-da-te. Intercetta l'interfaccia web originale iniettando codice tramite Chromium. Consigliata solo se non disponi di alcuna credenziale di accesso a CINECA. Ideale se *non* si dispone di un'utenza API CINECA. *Necessita di un calendario pubblico da aprire per fare lo scraping dei dati.*

* 🚀 [**Versione 2: REST API CINECA (Consigliata)**](Versione%202%20-%20REST%20API%20CINECA%20(Consigliata)/README.md) ([Guida Installazione Passo-Passo](Versione%202%20-%20REST%20API%20CINECA%20(Consigliata)/INSTALL.md)) - Metodo 'Native'. Interroga direttamente il DB di CINECA. Scelta consigliata per stabilità e prestazioni. Include persistenza degli annullamenti, mappatura dinamica degli edifici e un layout Responsive con menù interattivo. *Necessita delle credenziali di accesso a U-Planner.*

## Quale versione scegliere?

| Funzionalità | Versione 1 (Scraping) | Versione 2 (REST API - Consigliata) |
| :--- | :--- | :--- |
| **Metodo** | Iniezione DOM (Chromium) | Chiamata nativa REST API |
| **Credenziali** | **Nessuna richiesta** | Richiede Account U-Planner |
| **Stabilità** | Bassa (dipende dal layout web) | Alta (protocollo JSON) |
| **Persistenza** | No (stato volatile) | **Sì (salvataggio locale e tag "annullato/spostato" per modifiche live)** |
| **Risorse Hardware** | Elevato (Chrome è pesante) | **Minimo (Python Script)** |
| **Interfaccia Utente (UI)** | Fissa a due colonne (Desktop) | **Responsive Mobile & Desktop, Info Badge (Menu fluttuante)** |
| **Configurazione UI** | Modifica nel codice JS/HTML | **File `config.yaml` o Pannello Web (`/admin`)** |
| **Reattività Modifiche** | Riavvio fisico del Kiosk necessario | **Hot-Reload automatico in tempo reale senza interruzioni** |
| **Ticker Notizie / Locandine** | Assente | **Sì, integrabile con RSS/REST, ampiamente personalizzabile** |
| **Stati eventi UPlanner** | Mostra sempre solo P (Pubblicati) e C (Confermati), indisponibilità appaiono come "Attività Programmata" | **Mostra P (Pubblicati), C (Confermati), eventi Confermati sono disattivabili dalla vista, flagga eventi A (Annullati) come Annullati automaticamente, i pallini P e C sono visibili accanto al nome o disattivabili, gestisce le Indisponibilità mostrando il nome corretto** |
| **Stato del Progetto** | Legacy (Backup v1.x) | **Produzione Attiva (v5.0 - FINAL)** |
---

<br>
<br>
<p align="center">
  ♦ &nbsp; &nbsp; ♦ &nbsp; &nbsp; ♦
</p>
<br>
<br>

---

# Changelog

## [v5.0 - FINAL] - Produzione Live, Sicurezza HTTPS Nativa, Multi Monitor Support, Hub Preferenze e Nuovo Pannello Admin
Questa major release segna il completamento dello sviluppo e la prima versione ufficiale destinata alla messa in produzione live.

Introduce il supporto crittografico nativo HTTPS a doppio canale, rinnova totalmente il pannello di amministrazione e l'hub preferenze, ottimizza il Digital Signage multi-schermo, potenzia l'architettura con il multi-threading concorrente e introduce la nuova documentazione modulare e diagnostica.

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

## [v4.7] - Guida Porta HTTP 80, Integrazione Rete e Sicurezza Avvio Kiosk
Questa release semplifica l'accesso alla dashboard tramite porta standard (`80`) e previene disallineamenti di porta all'avvio del chiosco.
* **Guida Porta HTTP Standard (80):** Aggiunta sezione dedicata nel README della Versione 2 con tre metodologie (Port Redirection con `iptables`, Capability Linux `setcap`, e Reverse Proxy `nginx`) per accedere al totem via IP o DNS senza specificare la porta `:8080`.
* **Sincronizzazione Porta e `~/.xinitrc`:** Introdotto promemoria critico nella documentazione e nell'interfaccia di amministrazione web (`admin.html`) per ricordare di allineare l'URL del comando Chromium in `~/.xinitrc` ogni volta che viene modificata la porta server locale, prevenendo schermate di errore `ERR_CONNECTION_REFUSED` sul monitor fisico del Kiosk.

## [v4.6] - News Hub interattivo, Multi-Fonti e Fix Backend
Questa release introduce un'esperienza di consultazione delle notizie profondamente migliorata e risolve alcune criticità di salvataggio.
* **News Hub Modale:** Aggiunto un pulsante flottante `+` (con restyling in formato "pillola" SVG) così da permettere a chi accede da browser di aprire una finestra interattiva dove consultare tutte le notizie scaricate in una comoda tabella ordinabile alfabeticamente e per data (con frecce dinamiche ▲ / ▼).
* **Fonti Espansive e Peso:** Il sistema supporta ora l'immissione di fino a 6 fonti distinte contemporaneamente tramite il file YAML o dal pannello Admin. È stato aggiunto il parametro `peso` (da 1 a 5) per far apparire più o meno frequentemente una specifica fonte all'interno del nastro scorrevole.
* **Preferenze Locali (LocalStorage):** Gli utenti che accedono da PC o Smartphone possono disattivare alcune fonti news per la loro sessione locale. Le preferenze vengono salvate nel browser tramite LocalStorage senza impattare il totem pubblico, che continuerà a seguire le regole `visibile_di_default` dettate dall'amministratore.

## [v4.5] - Parametri Dinamici, UI Fixing e Scrolling Invisibile
Questa release rende l'applicazione completamente svincolata da parametri hardcoded, potenziando il limite di eventi caricati e raffinando il comportamento dell'interfaccia sia su schermi enormi che su smartphone.
* **Parametri CINECA 100% Dinamici:** I codici dell'Anno Accademico e del Contesto (Sede), in precedenza incorporati nel codice sorgente, sono stati estratti e resi dinamici per un utilizzo universale.
* **Aggiornamento Pannello Admin:** L'interfaccia di amministrazione Web (`/admin`) è stata arricchita con i nuovi campi dedicati per l'inserimento rapido di `Anno Accademico ID` e `Contesto ID`. 
* **Aumento Limite Eventi:** Il numero massimo di eventi interrogabili singolarmente dalle API CINECA è stato innalzato in sicurezza da 150 a 500, garantendo che nessun impegno sfugga alla visualizzazione durante le giornate eccezionalmente cariche.
* **Scrolling Invisibile e Fix Testi (Desktop):** Risolto il problema del "testo affettato" (in cui nomi di docenti lunghi venivano tagliati a metà dal layout in caso di colonna satura). È stato inoltre sbloccato lo scorrimento verticale naturale delle colonne tramite una scrollbar volutamente invisibile, perfetta per mantenere la pulizia visiva del digital signage.
* **Fix Allineamenti e Footer (Mobile):** Ottimizzati drasticamente i calcoli per schermi piccoli: corretto il fastidioso "salto" della pagina provocato dall'alternanza di notizie sul ticker, ri-allineato chirurgicamente il box degli avvisi e impedito che frasi lunghe allungassero a dismisura l'intero footer.
* **Titolo Agnostico:** Rimosso il suffisso accademico fisso dal tag `<title>` della pagina per completare il processo di universalità del progetto.
* **Guida Parametri Inclusa:** Aggiornata la documentazione con istruzioni chiare e passo-passo su come reperire in autonomia i codici di configurazione necessari ispezionando la console di CINECA Up.

## [v4.0] - Gestione Remota, Hot-Reload e Footer Informativo
Questa major release trasforma il Kiosk in uno strumento pienamente amministrabile da remoto.
* **Unificazioni variabili in un unico file config.yaml** tutte le personalizzazioni risiedono in un unico file `config.yaml`.
* **Pannello di Amministrazione Web:** Oltre alla scrittura manuale su config.yaml, è presente una **Nuova interfaccia grafica (`/admin`)** per modificare colori, testi, velocità e loghi senza toccare una riga di codice (il pannello di base è disattivato, ma può essere attivato da `config.yaml` in un secondo).
* **Hot-Reload e Resilienza:** I Kiosk in rete si aggiornano automaticamente in tempo reale ("a caldo") non appena si salva la configurazione dal pannello, senza bisogno di riavvii. Migliorata anche la ripresa automatica dopo cali di rete. 
* **Footer News Avanzato:** Introdotto un feed scorrevole personalizzabile (orizzontale o verticale) capace di integrarsi con API REST e RSS esterni. Le notizie sono cliccabili (con collegamento all'articolo originale). 
* **Gestione Locandine Intelligente:** Il carosello pubblicitario può ora essere disabilitato selettivamente (solo per il proprio browser) tramite il comodo badge informazioni, senza influenzare i monitor Kiosk di ateneo.
* **Log Centralizzati:** I file di log del sistema (`kiosk.log` e `server_api_sys.log`) sono ora generati direttamente nella cartella base `dashboard_aule` per un rapido accesso e agevolare il troubleshooting.

## [v3.5] - Gestione avanzata eventi UPlanner
Questa release affina ulteriormente la gestione dei dati provenienti da U-Planner, introducendo un controllo più preciso sugli stati degli eventi e migliorando la chiarezza delle informazioni esposte sulla dashboard.

### ✨ Novità e Miglioramenti
* **Gestione granulare degli Stati (P e C):** Il sistema ora distingue chiaramente gli eventi Pubblicati (P) da quelli Confermati (C). Appositi indicatori visivi (pallini) vengono mostrati accanto al nome dell'evento per identificarne lo stato; tali indicatori possono essere comodamente disattivati se non necessari.
* **Filtro Eventi Confermati:** È stata introdotta la possibilità di nascondere completamente dalla vista gli eventi in stato Confermato (C).
* **Annullamenti Automatici (A):** Gli eventi contrassegnati come Annullati (A) da U-Planner vengono ora rilevati nativamente e flaggati in automatico come tali sull'interfaccia.
* **Risoluzione delle Indisponibilità:** Le indisponibilità delle aule vengono processate in modo completo mostrando la loro causale reale, eliminando la precedente e anonima dicitura di "Attività programmata".

## [v3.0] - Responsive Design, UX Improvements & Logic Fixes
Questa versione introduce il pieno supporto ai dispositivi mobili, una revisione completa dell'interfaccia utente (UX) e importanti ottimizzazioni nella gestione dei dati lato server.

### ✨ Novità e Miglioramenti
* **Piena compatibilità Mobile:** Ristrutturazione del layout con CSS Grid e Flexbox per adattarsi perfettamente agli schermi degli smartphone. Introdotto il blocco dello scorrimento orizzontale e l'adattamento dinamico delle colonne.
* **Smart Data Reset:** **RISOLTO BUG:** Ottimizzata la logica di pulizia della cache in `server_api.py`. Gli eventi annullati o terminati non persistono più per 24 ore dall'orario di fine, ma vengono rimossi automaticamente allo scoccare della mezzanotte, garantendo un file JSON sempre pulito all'inizio di ogni nuova giornata.
* **Documentazione migliorata:** Separate le istruzioni per le varie versioni in vari file .md navigabili
* **Nuovo Cassetto Informativo Dinamico:** Inserito menu a scomparsa laterale che si adatta al dispositivo in uso. Su ambiente desktop è quasi invisibile in basso a destra e introduce tooltip personalizzati in puro CSS ad apparizione istantanea (eliminando la fastidiosa latenza dell'attributo title nativo). Su smartphone e tablet, il cassetto si trasforma in un menu verticale espandibile ottimizzato per il touch, con animazioni fluide e rotazione dinamica dell'icona, dove i tooltip "degradano con grazia" trasformandosi in comode descrizioni testuali inline.


### 🐛 Bug Fixes
* **Grid Blowout Fix:** Risolto il problema che causava l'allargamento spropositato delle schede (e la scomparsa del menu) in presenza di testi troppo lunghi, grazie all'implementazione accurata di `min-width: 0` e `minmax(0, 1fr)`.
* **Fix troncamento testi:** Garantito il corretto funzionamento dei puntini di sospensione (`text-overflow: ellipsis`) per titoli degli esami e nomi dei docenti eccessivamente lunghi.
* **Fix UI Desktop:** Risolto un bug visivo che causava l'impilamento verticale errato dei link all'interno del cassetto informativo su schermi desktop.
* **Fix False Hover su Mobile:** Disattivato l'effetto hover nativo sui dispositivi touch che bloccava la corretta chiusura del menu a scomparsa.

---

## [v2.0] - Architettura Client-Server & Integrazione API Ufficiale
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

---

## [v1.0] - Initial Release
* Prima versione stabile della dashboard per i display Kiosk.
* **Motore Base:** Sistema di reperimento dati basato esclusivamente sul metodo di *DOM Injection* dal calendario pubblico.
* Struttura visiva a colonne rigide (in corso / prossimi eventi) ottimizzata nativamente per schermi di grandi dimensioni (landscape o verticali) senza necessità di scorrimento.