# 📋 Guida e Legenda dei File di Log (`kiosk.log` e `server_api_sys.log`)

Questo documento descrive in dettaglio l'architettura dei log del sistema **Kiosk4UPlanner**, spiegando la differenza tra i due file generati sul dispositivo, l'elenco completo dei messaggi (operativi e di debug) e come interpretarli per la manutenzione e la diagnostica.

---

## 🗂️ 1. Architettura dei File di Log

Il sistema adotta una netta separazione tra i log applicativi del software e i log di sistema/interprete del sistema operativo Linux:

```text
[ Processo server_api.py + pacchetto core/ ]
       │
       ├────▶ logging (RotatingFileHandler 10 MB x 5) ─▶ kiosk.log (Log Applicativo)
       │
       └────▶ stdout / stderr (Bash redirection >>) ───▶ server_api_sys.log (Log di Sistema, ruotato a 5 MB)
```

### A. `kiosk.log` (Log Applicativo del Demone)
* **Percorso:** Definito in `config.yaml` (`main.file_log`, di default nella cartella del progetto).
* **Gestione e Rotazione:** Generato dal modulo standard `logging` di Python tramite `RotatingFileHandler` (massimo **10 MB** per file con 4 backup storici `kiosk.log.1`…`kiosk.log.4`, tetto complessivo **50 MB**).
* **Formato riga:**  
  `YYYY-MM-DD HH:MM:SS - [API SERVER] - [LIVELLO]: Messaggio`  
  dove `[LIVELLO]` può essere `INFO`, `WARNING` o `ERROR`.
* **Cosa contiene:** Il flusso di lavoro ordinario del sistema (`server_api.py` e moduli `core/`): avvio dei demoni, autenticazione e backoff esponenziale CINECA, sonda paginazione, scaricamento e sincronizzazione delle aule, reset giornaliero atomico delle 04:00 AM, lettura dei feed news, sicurezza/operazioni svolte dal pannello `/admin` e messaggi diagnostici.

### B. `server_api_sys.log` (Log di Basso Livello / Watchdog Bash)
* **Percorso:** Generato nel percorso specificato in `~/.xinitrc`.
* **Gestione e Rotazione:** Generato dal ciclo watchdog di avvio grafico in `~/.xinitrc`, con rotazione automatica a **5 MB** (`server_api_sys.log.1`) prima di ogni riavvio:
  ```bash
  while true; do
    LOG_SYS="$DIR_PROGETTO/server_api_sys.log"
    if [ -f "$LOG_SYS" ] && [ "$(stat -c%s "$LOG_SYS")" -gt 5242880 ]; then mv -f "$LOG_SYS" "$LOG_SYS.1"; fi
    python3 "$DIR_PROGETTO/server_api.py" >> "$LOG_SYS" 2>&1
    sleep 2
  done &
  ```
* **Stato normale:** In condizioni di corretto funzionamento deve rimanere **vuoto (0 byte)**.
* **Cosa contiene:** Tutto ciò che l'interprete Python o il sistema operativo scrivono direttamente sullo stream standard di errore (`stderr`) o di output (`stdout`), come ad esempio:
  - Errori irreversibili di avvio (moduli mancanti, errori di sintassi).
  - Eventuali crash improvvisi del processo (segnali di terminazione Linux, Out Of Memory).
  - Eccezioni non catturate a livello di socket server della libreria standard.

---

## 📖 2. Legenda di `kiosk.log`

I messaggi registrati in `kiosk.log` sono suddivisi in **Operativi Standard** (sempre visibili) e **Diagnostici Avanzati / Debug** (visibili solo abilitando `debug_mode: true` in `config.yaml` o da `/admin`).

---

### 🟢 Messaggi Standard / Operativi (`debug_mode: false`)

Questi messaggi rappresentano la normale attività del chiosco e dei motori `core/` a regime:

| Livello | Messaggio nel Log | Significato e Azione |
| :--- | :--- | :--- |
| **INFO** | `🚀 Avviato demone API CINECA (Modalità Admin Autenticata).` | Il thread di polling delle API CINECA è partito correttamente all'accensione del chiosco o al riavvio del processo. |
| **INFO** | `🚀 Avviato demone News (Footer).` | Il thread incaricato di scaricare i feed RSS/Atom e REST (confinato in RAM tramite `NewsEngine`) è attivo. |
| **INFO** | `Avvio KioskServer HTTP sulla porta 8080` | Il server web HTTP locale è pronto e in ascolto per servire la dashboard (`remoto.html`), gli asset `/static/*` e le API locali. |
| **INFO** | `Avvio KioskServer HTTPS (SSL) sulla porta 8443` | Il server web cifrato HTTPS su thread parallelo è attivo e in ascolto. |
| **WARNING** | `⚠️ HTTPS abilitato ma file certificato o chiave non trovati (...). Server HTTPS non avviato.` | L'HTTPS è stato impostato su `true` in `config.yaml`, ma i file `.pem` o `.key` non sono presenti nel percorso specificato. Il sistema disattiva il redirect forzato e continua regolarmente in HTTP (fail-safe). |
| **INFO** | `Richiesta di un nuovo Token a CINECA (Admin) in corso...` | `CinecaClient` sta contattando l'endpoint `/Utenti/login` di CINECA U-Planner (timeout 15s) per ottenere un token di sessione autenticato. |
| **INFO** | `✅ Login CINECA riuscito. Nuovo token acquisito.` | Le credenziali tecniche fornite sono corrette: CINECA ha rilasciato un nuovo token valido ed eventuali contatori di backoff sono stati azzerati. |
| **ERROR** | `❌ Errore Login CINECA (tentativo #N): [motivo]. Backoff attivato per Xs.` | Login respinto (es. `HTTP 401`, credenziali o `realm` errati) oppure errore/timeout di rete. `CinecaClient` attiva il **backoff esponenziale `N-05`** (`120s → 240s → 480s → 960s → 1920s → max 3600s` + jitter) per non bloccare l'utenza sull'IdP di Ateneo. |
| **WARNING** | `⏳ Login CINECA in backoff attivo: riprova tra Xs.` | Il ciclo di controllo si è risvegliato mentre la finestra di backoff esponenziale è ancora attiva: nessuna richiesta HTTP viene inviata a CINECA fino allo scadere dei secondi indicati. |
| **ERROR** | `❌ Token scaduto o non valido (401). Forzo il rinnovo.` | Il token di sessione precedentemente rilasciato è scaduto (tipicamente dopo 14 giorni). Il sistema lo invalida automaticamente e acquisisce un nuovo token al ciclo successivo (Self-Healing). |
| **INFO** | `ℹ️ Sonda paginazione CINECA: parametri skip/offset/page ignorati o rifiutati da CINECA UP. Attiva salvaguardia obbligatoria su anno_accademico_id e contesto_id.` | Esito standard all'avvio della sonda diagnostica (`v5.3.6`): poiché U-Planner ignora la paginazione su `getImpegniCalendario`, il server impone la compilazione di Anno Accademico e Contesto per evitare troncamenti a 500 eventi. *(Se un'istanza CINECA supportasse la paginazione, comparirebbe `✅ Sonda paginazione CINECA: parametro '...' supportato.`).* |
| **INFO** | `✅ Dati ricevuti da CINECA! Trovati X impegni.` | Sincronizzazione completata: dopo il filtro locale per `id_edificio` e stati selezionati, sono disponibili `X` impegni attivi o futuri per la giornata operativa corrente. |
| **INFO** | `🛡️ Nessun nuovo dato CINECA: X impegni precedenti mantenuti a video.` | Attivata la protezione anti-falsi annullamenti (`D-01`, accompagnata dal warning `⚠️ Rilevato payload CINECA vuoto a fronte di impegni validi in memoria...`): il tabellone conserva intatti gli ultimi impegni validi. |
| **INFO** | `🚫 Impegno [ID] assente da CINECA per 2 polling consecutivi: marcato ANNULLATO.` | Motore `D-01`: una lezione futura non ancora conclusa è risultata assente per 2 cicli consecutivi riusciti ed è stata confermata come `ANNULLATO` (se dovesse riapparire, verrà ripristinata automaticamente in auto-healing). |
| **WARNING** | `⚠️ SENTINELLA LIMITE CINECA: ricevuti 500 impegni (limite 500). Possibile troncatura: valorizzare anno_accademico_id e contesto_id.` | La risposta grezza di CINECA ha toccato il tetto massimo di 500 impegni per chiamata: verificare in `/admin` che `anno_accademico_id` e `contesto_id` circoscrivano correttamente il Polo/Dipartimento. |
| **WARNING** | `⚠️ Impegno CINECA [ID] non interpretabile (...): stato precedente preservato.` | Un singolo record restituito da CINECA presenta campi orari/strutturali anomali: viene ignorato senza cancellare né marcare come annullato lo stato precedente. |
| **INFO** | `🔄 Esecuzione reset giornaliero impegni (precedente: YYYY-MM-DD -> nuovo giorno operativo: YYYY-MM-DD).` | `BuildingContext` ha azzerato lo storico della giornata precedente salvando atomicamente `stato_impegni.json` e `ultimo_reset.txt` (`ST-11.1`). È seguito da `🧹 Catch-up avvio: ...` se eseguito all'accensione mattutina, oppure da `🌅 Eseguito reset delle 04:00 AM. Avvio scaricamento orari fresco.` se scattato alle 04:00 AM. |
| **ERROR** | `❌ Errore durante il salvataggio atomico dello stato: ...` | Impossibile scrivere o sostituire atomicamente `stato_impegni.json` su disco (verificare spazio libero e permessi sulla MicroSD; analoghi warning compaiono per `ultimo_reset.txt` o file di stato corrotti). |
| **ERROR** | `❌ Errore HTTP 500/503: ...` | I server CINECA hanno risposto con un errore interno (es. manutenzione straordinaria dei server di Ateneo). Il chiosco mantiene a video l'ultimo stato valido. |
| **ERROR** | `❌ Errore critico nel ciclo API: ...` | Errore transitorio di rete o timeout durante il ciclo di recupero orari. Il demone non si interrompe e riprova dopo l'intervallo configurato. |
| **WARNING** | `⚠️ Errore recupero news da [Nome] ([URL]): ...` | Una singola fonte RSS/Atom/REST ha superato il timeout di 5s o restituito errore HTTP/XML/JSON: `NewsEngine` la marca con semaforo 🔴 in `/admin` e prosegue regolarmente con le altre fonti. |
| **ERROR** | `❌ Errore critico demone News: ...` | Errore imprevisto nel thread del footer notizie; viene intercettato senza causare il crash del server. |
| **WARNING** | `🚨 Troppi tentativi di login errati dall'IP [IP]. IP bloccato per 10 minuti.` | Rate-limiter atomico (`ST-10.3`): l'indirizzo IP indicato ha raggiunto 5 tentativi di accesso errati su `/api/admin/login` ed è temporaneamente bloccato (`HTTP 429`) per 600 secondi. |
| **INFO** | `💾 Configurazione salvata e applicata con successo da /admin.` | Le modifiche inviate dal pannello `/admin` hanno superato la validazione a whitelist, sono state scritte atomicamente in `config.yaml` e applicate a caldo in memoria. |
| **WARNING** | `🚫 Errore salvataggio config (payload rifiutato): ...` | Validazione `N-10` / ID CINECA: `/api/admin/save` ha respinto con `HTTP 400` un payload contenente chiavi non autorizzate, porte fuori range, formati ID non validi o tentativi di path traversal. |
| **WARNING** | `🚫 Errore salvataggio config: anno_accademico_id e contesto_id obbligatori quando la paginazione CINECA non è supportata.` | Salvaguardia `v5.3.6`: tentativo di salvare credenziali CINECA attive lasciando vuoti Anno Accademico o Contesto con `Debug Mode` disattivo. *(Con `Debug Mode` attivo compare invece `🕵️ Salvataggio temporaneo consentito senza anno_accademico_id/contesto_id perché Debug Mode è attiva...`).* |
| **INFO** | `🖼️ Locandina caricata: p<epoch>_<hex>.<ext> (X KB).`<br>`🗑️ Locandina eliminata: [nome_file]` | Conferma del caricamento streaming binario (validato tramite magic bytes JPEG/PNG/WebP) o della rimozione sicura di una locandina da `/admin`. |
| **INFO** | `Riavvio richiesto dall'Admin. Termino il processo (il watchdog Bash lo riavvierà).` | Dal pannello web `/admin` è stato cliccato il pulsante "Salva e Riavvia". Il processo Python termina regolarmente con codice 0 e lo script Bash `~/.xinitrc` lo riavvia entro 2 secondi. |
| **ERROR** | `Errore critico avvio server HTTP: ...` / `Errore critico avvio server HTTPS: ...` | Impossibile avviare il socket di ascolto web (es. porta `8080`/`8443` già occupata, certificato SSL illeggibile o tentativo di aprire la porta `80` senza privilegi/capability). |

---

### 🕵️ Messaggi di Diagnostica Avanzata (`debug_mode: true`)

Attivando la voce `debug_mode: true` in `config.yaml` (oppure spuntando **Abilita Debug Mode** in `/admin` → scheda *Sistema e Rete* → tendina *Credenziali e Connessione CINECA*), compaiono righe diagnostiche precedute dall'icona 🕵️ per ispezionare il traffico API e scoprire automaticamente gli ID di configurazione CINECA:

| Livello | Messaggio nel Log | Significato e Utilità Pratica |
| :--- | :--- | :--- |
| **INFO** | `🕵️ DEBUG MAPPA ANNI ACCADEMICI RILEVATI (N): ["2026/2027 (cod. '2026') -> ID '5fefef...' [ANNO IN CORSO]", ...]` | **Auto-discovery degli Anni Accademici:** interroga `/AnniAccademici` all'attivazione del Debug Mode (e all'avvio) stampando tutti gli anni presenti su U-Planner con relativo ID esadecimale di 24 caratteri, evidenziando `[ANNO IN CORSO]` e `[IN USO]`. Utile sia alla prima installazione sia al cambio annuale di A.A. |
| **INFO** | `🕵️ DEBUG MAPPA CONTESTI RILEVATI (N): ["Codice 'Polo A' (Polo Centrale) -> ID '5b9778...' [IN USO]", ...]` | **Auto-discovery dei Contesti:** interroga `/Contesti` stampando tutti i Poli didattici, Dipartimenti e contesti trasversali dell'Ateneo con codice, nome leggibile e ID di 24 caratteri da inserire in `contesto_id`. |
| **INFO** | `🕵️ DEBUG: anno_accademico_id o contesto_id non ancora configurati. Copia gli ID dalle mappe...` | Compare quando si usa il Debug Mode in fase di prima installazione con Anno o Contesto ancora vuoti, ricordando di copiare i due ID appena stampati sopra per abilitare lo scaricamento orari. |
| **INFO** | `🕵️ DEBUG: Richiesta impegni a [URL] (Payload: {...})` | Mostra ad ogni ciclo i parametri esatti inviati a `getImpegniCalendario`: orari UTC di inizio/fine giornata, `limit`, `annoAccademicoId`, `contestoId` e opzioni di visualizzazione. |
| **INFO** | `🕵️ DEBUG: Ricevuti X impegni grezzi.` | Mostra il numero **totale** di impegni restituiti da CINECA per l'intero Contesto prima del filtro locale per `id_edificio`. Se è `0`, non ci sono eventi per la data oppure `contestoId`/`annoAccademicoId` non sono valorizzati o corretti. |
| **INFO** | `🕵️ DEBUG MAPPA EDIFICI RILEVATI (N): ["Codice '01': Sede Centrale", "Codice '05': San Felice", ...]` | **Auto-discovery degli Edifici:** ispeziona gli impegni grezzi del giorno ed elenca ogni codice edificio rilevato con la sua descrizione, permettendo di individuare subito il valore da inserire in `id_edificio`. |
| **INFO** | `🕵️ DEBUG MAPPA EDIFICI: Nessun edificio rilevato negli impegni grezzi ricevuti.` | Compare se nella giornata corrente non ci sono lezioni con aula/edificio associato (o prima di aver configurato `contesto_id`). |

> [!TIP]
> **Come trovare Anno Accademico, Contesto ed Edificio con il Debug Mode (senza usare `F12`):**
> 1. In `/admin` → scheda *Sistema e Rete* → tendina *Credenziali e Connessione CINECA* (o in `config.yaml`), inserisci `Username`, `Password` e `Realm`, spunta **Abilita Debug Mode** subito sotto il box guida e salva.
> 2. Esegui `grep "DEBUG MAPPA" ~/dashboard_aule/kiosk.log`: troverai subito gli elenchi `MAPPA ANNI ACCADEMICI` e `MAPPA CONTESTI` con i rispettivi ID di 24 caratteri.
> 3. Incolla `ID Anno Accademico` e `ID Contesto` (scegliendo il *Polo* se l'edificio è condiviso da più Dipartimenti), salva e attendi un ciclo per leggere anche `MAPPA EDIFICI`.
> 4. Inserisci `ID Edificio` (es. `"05"`), **disattiva il Debug Mode** e salva. *(In alternativa, la procedura manuale via browser `F12` — inclusa la ricerca iniziale del `Realm` — è descritta nella **[Sezione 4 di INSTALL.md](INSTALL.md#4-configurazione-credenziali-cineca)**).*

---

## 🛑 3. Legenda di `server_api_sys.log`

Questo file raccoglie le anomalie a basso livello del sistema operativo e dell'interprete Python. In condizioni normali deve avere dimensione pari a **0 byte (completamente vuoto)**.

> [!NOTE]
> **Perché questo elenco non è (e non può essere) esaustivo?**  
> A differenza di `kiosk.log`, in cui i messaggi sono stringhe controllate e definite a priori nel codice sorgente con `logging.info()` o `logging.error()`, `server_api_sys.log` cattura lo stream grezzo di errore (`stderr`) dell'intero ambiente Linux e dell'interprete Python.  
> Qualsiasi eccezione non gestita produrrà uno **stack trace dinamico**, le cui righe dipendono dallo specifico file di sistema, modulo o riga di codice che ha fallito. Di conseguenza, la tabella seguente riporta le casistiche più comuni e rilevanti riscontrate nella pratica, ma non può coprire ogni possibile errore teorico di Python o del sistema operativo.

### 🔍 Come interpretare un blocco di errore (Python Traceback)

Quando si verifica un errore, Python stampa un blocco di testo multilinea (Traceback). Ecco un esempio reale riscontrato nei log:

```text
----------------------------------------
Exception occurred during processing of request from ('103.126.10.226', 63267)
Traceback (most recent call last):
  File "/usr/lib/python3.11/socketserver.py", line 317, in _handle_request_noblock
    self.process_request(request, client_address)
  File "/usr/lib/python3.11/socketserver.py", line 348, in process_request
    self.finish_request(request, client_address)
  ...
  File "/usr/lib/python3.11/socket.py", line 706, in readinto
    return self._sock.recv_into(b)
ConnectionResetError: [Errno 104] Connection reset by peer
----------------------------------------
```

Per interpretarlo rapidamente:
1. **Intestazione:** `Exception occurred during processing of request from ('IP', porta)` indica l'indirizzo IP del client che ha originato la connessione.
2. **Corpo centrale:** Le righe `File "...", line ...` mostrano la sequenza interna delle chiamate nelle librerie di sistema.
3. **Ultima riga (LA PIÙ IMPORTANTE):** Riporta sempre il nome dell'eccezione finale e la causa effettiva (in questo esempio: `ConnectionResetError: [Errno 104] Connection reset by peer`).

---

### 📋 Principali casistiche riscontrabili

| Sintomo / Errore in `server_api_sys.log` | Causa Radice | Soluzione e Stato |
| :--- | :--- | :--- |
| `ConnectionResetError: [Errno 104] Connection reset by peer`<br>`BrokenPipeError: [Errno 32] Broken pipe`<br>`ConnectionAbortedError` / `TimeoutError` | Uno scanner bot esterno o un client ha interrotto bruscamente la connessione TCP oppure ha lasciato il socket inattivo oltre il timeout di sicurezza di 15s (`ST-08`). | **Risolto nativamente nel codice:** il server multi-thread (`KioskHTTPServer`) con semaforo a 40 slot intercetta in `handle_error` disconnessioni premature e timeout socket, evitando che sporchino il log o saturino i thread. |
| `ModuleNotFoundError: No module named 'yaml'` (oppure `'requests'` / `'core'`) | Python è stato avviato senza le dipendenze di sistema installate, oppure la sottocartella `core/` non è stata copiata accanto a `server_api.py`. | Eseguire su Raspberry: <br>`sudo apt install python3-requests python3-yaml` e verificare la presenza di `~/dashboard_aule/core/`. |
| `SyntaxError: invalid syntax` / `IndentationError` | File Python (`server_api.py` o moduli in `core/`) corrotti o copiati con interruzioni di riga Windows (`CRLF`). | Eseguire su Raspberry: <br>`sudo apt install dos2unix && dos2unix ~/dashboard_aule/server_api.py ~/dashboard_aule/core/*.py` |
| `PermissionError: [Errno 13] Permission denied` | Permessi insufficienti per scrivere `kiosk.log` o `stato_impegni.json`, oppure tentativo di aprire porte riservate (< 1024) senza privilegi root. | Assegnare i permessi corretti all'utente:<br>`chown -R $USER:$USER /home/vincenzo/dashboard_aule` |
| `Killed` / `Out of memory` | Il kernel Linux (OOM-Killer) ha forzato la chiusura del processo Python per esaurimento della memoria RAM fisica. | Verificare che la memoria del Raspberry non sia saturata da processi Chromium orfani o memory leak. |
| `[Errno 16] Device or resource busy` | La scheda di rete fisica (Wi-Fi `wlan0` o driver Ethernet) si è bloccata o è andata in standby per risparmio energetico. | Disabilitare il risparmio energetico Wi-Fi con:<br>`sudo iwconfig wlan0 power off` |


---

## 🛠️ Comandi Utili per il Controllo Rapido dei Log su Linux

Per monitorare i log in tempo reale direttamente da terminale SSH sul Raspberry Pi:

* **Seguire i log operativi in tempo reale:**
  ```bash
  tail -f /home/vincenzo/dashboard_aule/kiosk.log
  ```
* **Filtrare solo gli errori recenti:**
  ```bash
  grep "ERROR" /home/vincenzo/dashboard_aule/kiosk.log | tail -n 20
  ```
* **Controllare se ci sono messaggi di errore di sistema:**
  ```bash
  cat /home/vincenzo/dashboard_aule/server_api_sys.log
  ```
* **Filtrare tutte le mappe di auto-discovery CINECA (Anni Accademici, Contesti ed Edifici):**
  ```bash
  grep "DEBUG MAPPA" /home/vincenzo/dashboard_aule/kiosk.log
  ```
