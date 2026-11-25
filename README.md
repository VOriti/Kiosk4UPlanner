# Kiosk4Uplanner - Dashboard Kiosk Informativa

*Sviluppato per l'Università di Pavia (UNIPV)*

**Versione:** 5.3 (in sviluppo verso v6.0) | **Autore:** [Vincenzo Oriti](https://oriti.net) ([vincenzo.oriti@unipv.it](mailto:vincenzo.oriti@unipv.it)) | **Progetto:** [GitHub](https://github.com/VOriti/Kiosk4UPlanner) | **Licenza:** [CC BY-NC-SA 4.0](LICENSE.txt) ([Testo completo](https://creativecommons.org/licenses/by-nc-sa/4.0/))

---

Questo progetto trasforma un Raspberry Pi in una postazione **Kiosk informativa**, da installare negli atri di un polo universitario per mostrare a studenti e docenti lo stato di occupazione delle aule in tempo reale.

Ha principalmente tre funzioni:
- mostra **l'occupazione in tempo reale delle aule** del palazzo;
- ogni tot minuti **mostra eventuali locandine di eventi in corso o futuri**;
- **rende disponibili i dati su una pagina web all'interno della rete locale**. In questo modo, il personale può controllare l'occupazione corrente delle aule direttamente dal browser del proprio PC o Smartphone.

Il repository è diviso in **due versioni** indipendenti, per adattarsi ai livelli di accesso a disposizione della struttura:

* 📖 [**Versione 1: Scraping DOM (Senza API)**](Versione%201%20-%20Scraping%20DOM%20(Senza%20API)/README.md) - Soluzione fai-da-te. Intercetta l'interfaccia web originale iniettando codice tramite Chromium. Consigliata solo se non disponi di alcuna credenziale di accesso a CINECA. Ideale se *non* si dispone di un'utenza API CINECA. *Necessita di un calendario pubblico da aprire per fare lo scraping dei dati.*

* 🚀 [**Versione 2: REST API CINECA (Consigliata)**](Versione%202%20-%20REST%20API%20CINECA%20(Consigliata)/README.md) ([Guida Installazione Passo-Passo](Versione%202%20-%20REST%20API%20CINECA%20(Consigliata)/INSTALL.md)) - Metodo 'Native'. Interroga direttamente il DB di CINECA. Scelta consigliata per stabilità e prestazioni. Include persistenza degli annullamenti, auto-discovery dinamica in Debug Mode di anni accademici, contesti ed edifici (oltre alla guida F12 in `INSTALL.md`) e un layout Responsive con menù interattivo. *Necessita delle credenziali di accesso a U-Planner.*

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
| **Stato del Progetto** | Legacy (Backup v1.x) | **Produzione Attiva (v5.3 - in evoluzione verso v6.0)** |

---

## 🗺️ Roadmap Evolutiva verso la v6.0-FINAL

A seguito del rilascio della **v5.0 - FINAL** e delle prime sessioni di collaudo e test sul campo nei poli universitari, è stata definita una strategia di sviluppo sequenziale suddivisa su rami dedicati per traghettare il progetto verso la nuova release enterprise **v6.0-FINAL**:

```text
┌─────────────────┐       ┌──────────────────────────┐       ┌──────────────────────────┐
│  v5.0 - FINAL   │ ────> │     fix/backend-5.1      │ ────> │   feature/frontend-5.2   │
│(Produzione Live)│       │  (v5.1 Hardening & Fix)  │       │ (v5.2 Frontend & Media)  │
└─────────────────┘       └────────────┬─────────────┘       └────────────┬─────────────┘
                                       │                                  │
                                (Merge su main)                    (Merge su main)
                                                                          │
              ┌───────────────────────────────────────────────────────────┘
              ▼
┌─────────────┬──────────────┐       ┌────────────────────────────┐       ┌─────────────────┐
│refactor/core-decoupling-5.3│ ────> │ feature/campus-edition-5.4 │ ────> │  v6.0 - FINAL   │
│(v5.3 Modular Core Decoupl.)│       │(v5.4 Multi-Tenant & SQLite)│       │(Campus Edition) │
└─────────────┬──────────────┘       └─────────────┬──────────────┘       └────────┬────────┘
              │                                    │                               ▲
       (Merge su main)                      (Merge su main)                 (Tag Ufficiale)
```

1. **Milestone v5.1 (`fix/backend-5.1`) — Backend Hardening & Resilienza Server (COMPLETATA):**  
   13 interventi strutturali (10 mini-commit sequenziali + 1 fix scoping a HEAD + 1 consolidamento post-collaudo + 1 hotfix v5.1.12 CINECA auto-healing) focalizzati sulla robustezza infrastrutturale: protezione anti-flicker DOM con riconciliazione selettiva, reset orari alle 04:00 AM (fuso Roma) con catch-up all'avvio, scrittura atomica `.tmp` e zero-write su MicroSD via hash SHA-256, circuit-breaker anti-falsi annullamenti CINECA su 2 cicli, rate-limiter login (5 tentativi / 10 min) con countdown live, rotazione log a 50 MB, thread-safety Copy-on-Write su CONFIG (con fix scoping globale), supporto locandine PNG/WEBP con path guard, hardening HTTP difensivo (limite payload e header OWASP), parser RSS bi-direzionale compatibile sia con Drupal Views che WordPress con normalizzazione date `DD/MM/YYYY`, ordinamento cronologico news e diagnostica circuit-breaker affinata.
2. **Milestone v5.2 (`feature/frontend-5.2`) — Frontend, Gestione Media HD & News Hub UX (COMPLETATA):**  
   10 mini-commit per la trasformazione della dashboard e del carosello multimediale: streaming binario locandine con nomi immutabili `p<epoch>_<hex>`, ordine logico `ordine.json` atomico e cancellazione singola senza rinomine fisiche, cache browser permanente (`immutable`), ridimensionamento client Canvas (max 2160px WebP) e toast non bloccanti, carosello a rotazione a staffetta con duty-cycle configurabile (slider 10-50% in `/admin` per garantire precedenza assoluta agli orari), instant dismiss al tocco/clic/Escape, Kiosk Lockdown anti-vandalismo (`pointer-events: none` sui link esterni e inattività 60s), endpoint `/stato` con badge di freschezza CINECA in tempo reale, classificazione orari dinamica in RAM, conservazione tabellone orari su anomalie di rete, timeout 5s news con pesi 1-5 e parsing XML nativo da byte, semaforo diagnostico fonti in `/admin` (🟢/🔴/⚪ con conteggio articoli ed errori HTTP), ricerca dinamica full-text con debounce nel News Hub, sanitizzazione unificata `escapeHTML()` anti-XSS, miniature lazy e lightbox in `/admin`, e percorsi relativi `./` con template `config.example.yaml`.
3. **Milestone v5.3 (`refactor/core-decoupling-5.3`) — Disaccoppiamento del Core, Modularizzazione & CSP Hardening (COMPLETATA):**  
   6 mini-commit per la riorganizzazione modulare secondo l'**Opzione 1 (`D-19`)**: creazione del pacchetto backend `dashboard_aule/core/` con i motori autonomi `cineca_client.py` (`CinecaClient` con backoff esponenziale `120s → 3600s` per `N-05`, timeout `15s` e motore annullamenti `D-01`), `news_engine.py` (`NewsEngine` confinato interamente in RAM a zero I/O su MicroSD con semaforo diagnostico) e `building_context.py` (`BuildingContext` con `fsync` scorporato fuori dal lock di memoria `ST-09`, scrittura atomica di `ultimo_reset.txt` `ST-11.1` e pipeline locandine protetta); hardening di `server_api.py` come router HTTP snello con timeout socket `15s` e semaforo `BoundedSemaphore(40)` (`ST-08`), rate-limiter login atomico (`ST-10.3`) e validazione rigorosa a whitelist su `/api/admin/save` (`N-10`); estrazione integrale di JS e CSS nella sottocartella `dashboard_aule/static/` (`remoto.js`, `remoto.css`, `admin.js`, `admin.css`) serviti su `/static/*` e attivazione della `Content-Security-Policy` rigorosa (`SEC-06`); sonda paginazione CINECA con salvaguardia obbligatoria su `anno_accademico_id` e `contesto_id`, auto-discovery estesa in `Debug Mode` (Anni Accademici, Contesti ed Edifici) e restyling di `/admin`.
4. **Milestone v5.4 (`feature/campus-edition-5.4`) — Campus Edition, Multi-Tenancy & SQLite WAL:**  
   13 mini-commit per l'architettura enterprise di Ateneo e la transizione all'**Opzione 3 (`D-19`)** con separazione netta tra codice applicativo immutabile `app/` (`core/`, `templates/`, `static/`) e dati runtime scrivibili `data/` (`logs/`, `certs/`, `buildings/<slug>/`, `kiosk.db`) dotata di migrazione automatica dal layout `v5.3` e shim retrocompatibile `server_api.py` per `.xinitrc`: database SQLite WAL mode su storage locale verificato (`D-13`), autenticazione PBKDF2 dual-verify e modello RBAC N:M gerarchico (`campus_manager` per Logistica/Aule e `building_manager` di presidio), routing simmetrico `/:slug/` e `/admin/:slug/` con risoluzione sicura `trusted_proxies` (`D-12`), Hub panoramica `/admin/tenants/` e Console Master `/admin/campus/` (`campus.html`), segregazione locandine per tenant e Locandina Globale di Ateneo, visual health status cards e log streaming scoped, motore backup/restore YAML a 3 livelli, architettura reset a 3 livelli, selettore runtime unificato `--mode=department|campus`, CINECA Cache Broker centralizzato, script thin-client `.xinitrc.thinclient` con riavvio notturno Chromium (`D-18`) e overlayroot, e guide ufficiali di produzione (`INSTALL_DEPARTMENT.md`, `INSTALL_CAMPUS.md`).
5. **Traguardo Finale: Major Release v6.0-FINAL (Campus Edition Ready & Dual-Edition Convergence):**  
   Chiusura del ciclo evolutivo con merge formale su `main` e apposizione del tag annotato `v6.0-FINAL` (o `v6.0.0`): convergenza delle due edizioni (Department Edition standalone per Raspberry Pi e Campus Edition multi-tenant per server Debian di Ateneo) su un unico codebase unificato privo di fork, certificata per l'entrata in esercizio di produzione presso un Ateneo che lo adotti.

---

<br>
<p align="center">
  ♦ &nbsp; &nbsp; ♦ &nbsp; &nbsp; ♦
</p>
<br>

---

# 📜 Registro delle Versioni (Changelog)

Di seguito è riportata la sintesi delle release principali. Per il registro analitico con l'analisi tecnica dettagliata di ogni singolo commit, consulta il documento completo:  
👉 **[CHANGELOG.md](CHANGELOG.md)**

| Versione | Ramo / Branch | Focus & Sintesi Architetturale | Dettagli Completi |
| :---: | :--- | :--- | :---: |
| **[v5.3](CHANGELOG.md#v53---disaccoppiamento-del-core-modularizzazione--csp-hardening)** | `refactor/core-decoupling-5.3` | **Disaccoppiamento del Core, Modularizzazione & CSP Hardening:** 6 interventi (pacchetto `core/` con `cineca_client.py` e backoff esponenziale `N-05`, `news_engine.py` confinato in RAM zero-I/O, `building_context.py` con `fsync` fuori lock `ST-09` e reset atomico `ST-11.1`; hardening `server_api.py` con semaforo 40 slot/timeout 15s `ST-08`, login atomico `ST-10.3` e whitelist `/api/admin/save` `N-10`; asset JS/CSS estratti in `static/` secondo Opzione 1 `D-19` e `Content-Security-Policy` `SEC-06`; sonda paginazione CINECA, salvaguardia obbligatoria Anno/Contesto, auto-discovery in `Debug Mode` e restyling `/admin`). | [Vedi v5.3 ➔](CHANGELOG.md#v53---disaccoppiamento-del-core-modularizzazione--csp-hardening) |
| **[v5.2](CHANGELOG.md#v52---frontend-media-hd-news-hub-ux--kiosk-lockdown)** | `feature/frontend-5.2` | **Frontend, Media HD, News Hub UX & Kiosk Lockdown:** 10 interventi (upload streaming binario, nomi immutabili `p<epoch>_<hex>`, ordine logico `ordine.json`, cache browser permanente, downscaling Canvas 2160px WebP, Kiosk Lockdown con dismiss immediato al tocco/ESC e duty-cycle carosello 10-50%, endpoint `/stato` con badge freschezza CINECA, tabellone resiliente, timeout 5s news, semaforo diagnostico fonti in `/admin`, sanitizzazione `escapeHTML()` anti-XSS, ricerca News Hub, miniature lazy/lightbox e percorsi relativi `./`). | [Vedi v5.2 ➔](CHANGELOG.md#v52---frontend-media-hd-news-hub-ux--kiosk-lockdown) |
| **[v5.1](CHANGELOG.md#v51---backend-hardening--security-stability)** | `fix/backend-5.1` | **Backend Hardening & Sicurezza:** 13 interventi strutturali (10 mini-commit sequenziali + 1 fix scoping a HEAD + 1 consolidamento post-collaudo + 1 hotfix v5.1.12 CINECA auto-healing: rendering DOM selettivo, reset orari 04:00 fuso Roma, salvaguardia MicroSD atomica/condizionale, anti-falsi annullamenti CINECA su 2 cicli, rate-limiter login con countdown live, rotazione log 50MB, thread-safety Copy-on-Write, upload locandine protetto, hardening HTTP, parser RSS universale con date `DD/MM/YYYY`, ordinamento news e log affinati). | [Vedi v5.1 ➔](CHANGELOG.md#v51---backend-hardening--security-stability) |
| **[v5.0 - FINAL](CHANGELOG.md#v50---final---produzione-live-https-nativo-multi-monitor-admin-accordion)** | `main` | **[PRIMA VERSIONE DI PRODUZIONE LIVE] & HTTPS Nativo:** Server dual-stack HTTP/HTTPS, soppressione errori socket bot, bypass totem locale, interfaccia admin con tendine ad accordion, hub preferenze responsive, parametro `?kiosk=1`, parser RSS universale e documentazione modulare (`LEGENDA_LOG.md`, `INSTALL.md`). | [Vedi v5.0 ➔](CHANGELOG.md#v50---final---produzione-live-https-nativo-multi-monitor-admin-accordion) |
| **[v4.7](CHANGELOG.md#v47---guida-porta-http-80-integrazione-rete-e-sicurezza-avvio-kiosk)** | `main` | **Porta Standard (80) & Allineamento:** Guida completa alla porta 80 (`iptables`, `setcap`, `nginx`) e sincronizzazione all'avvio con `~/.xinitrc` per prevenire errori `ERR_CONNECTION_REFUSED`. | [Vedi v4.7 ➔](CHANGELOG.md#v47---guida-porta-http-80-integrazione-rete-e-sicurezza-avvio-kiosk) |
| **[v4.6](CHANGELOG.md#v46---news-hub-interattivo-multi-fonti-e-fix-backend)** | `main` | **News Hub Interattivo & Multi-Fonti:** Modale notizie ordinabile, supporto fino a 6 fonti RSS contemporanee con pesi di visualizzazione differenziati, aggiornamento sintassi RSS per compatibilità sia con WordPress che con Drupal Views, e preferenze utente in `localStorage`. | [Vedi v4.6 ➔](CHANGELOG.md#v46---news-hub-interattivo-multi-fonti-e-fix-backend) |
| **[v4.5](CHANGELOG.md#v45---parametri-dinamici-ui-fixing-e-scrolling-invisibile)** | `main` | **Parametri Dinamici & UI Polish:** Anno accademico e contesto CINECA dinamici da web admin, tetto a 500 eventi, scrollbar naturale invisibile e correzione salto footer su mobile. | [Vedi v4.5 ➔](CHANGELOG.md#v45---parametri-dinamici-ui-fixing-e-scrolling-invisibile) |
| **[v4.0](CHANGELOG.md#v40---gestione-remota-hot-reload-e-footer-informativo)** | `main` | **Pannello Web Admin & Hot-Reload:** Configurazione centralizzata in `config.yaml`, interfaccia grafica `/admin`, aggiornamenti live senza riavvio del browser e footer con news ticker. | [Vedi v4.0 ➔](CHANGELOG.md#v40---gestione-remota-hot-reload-e-footer-informativo) |
| **[v3.5](CHANGELOG.md#v35---gestione-avanzata-eventi-uplanner)** | `main` | **Stati UPlanner Avanzati:** Distinzione eventi Pubblicati (P) e Confermati (C), filtro visibilità, flag automatico eventi Annullati (A) e causali reali di indisponibilità aula. | [Vedi v3.5 ➔](CHANGELOG.md#v35---gestione-avanzata-eventi-uplanner) |
| **[v3.0](CHANGELOG.md#v30---responsive-design-ux-improvements--logic-fixes)** | `main` | **Responsive Design & Drawer:** Layout fluido CSS Grid/Flexbox per smartphone, pulizia automatica cache dati a mezzanotte e nuovo cassetto informativo a scomparsa. | [Vedi v3.0 ➔](CHANGELOG.md#v30---responsive-design-ux-improvements--logic-fixes) |
| **[v2.0](CHANGELOG.md#v20---architettura-client-server--integrazione-api-ufficiale)** | `main` | **Nascita Versione 2 (REST API):** Introduzione del demone backend Python (`server_api.py`), autenticazione diretta CINECA, persistenza in `stato_impegni.json` e rilevamento spostamenti aule. | [Vedi v2.0 ➔](CHANGELOG.md#v20---architettura-client-server--integrazione-api-ufficiale) |
| **[v1.0](CHANGELOG.md#v10---initial-release-scraping-dom---legacy)** | `legacy` | **Release Iniziale (Legacy):** Visualizzazione su totem basata unicamente su *DOM Injection* dal calendario web pubblico tramite istanza Chromium. | [Vedi v1.0 ➔](CHANGELOG.md#v10---initial-release-scraping-dom---legacy) |
