# 📋 Guida e Legenda dei File di Log (`kiosk.log` e `server_api_sys.log`)

Questo documento descrive in dettaglio l'architettura dei log del sistema **Kiosk4UPlanner**, spiegando la differenza tra i due file generati sul dispositivo, l'elenco completo dei messaggi (operativi e di debug) e come interpretarli per la manutenzione e la diagnostica.

---

## 🗂️ 1. Architettura dei File di Log

Il sistema adotta una netta separazione tra i log applicativi del software e i log di sistema/interprete del sistema operativo Linux:

```text
[ Processo server_api.py ]
       │
       ├────▶ logging (Python standard) ───────────────▶ kiosk.log (Log Applicativo)
       │
       └────▶ stdout / stderr (Bash redirection >>) ───▶ server_api_sys.log (Log di Sistema)
```

### A. `kiosk.log` (Log Applicativo del Demone)
* **Percorso:** Definito in `config.yaml` (`main.file_log`, di default nella cartella del progetto).
* **Gestione:** Generato nativamente dal modulo standard `logging` di Python.
* **Formato riga:**  
  `YYYY-MM-DD HH:MM:SS - [API SERVER] - [LIVELLO]: Messaggio`  
  dove `[LIVELLO]` può essere `INFO`, `WARNING` o `ERROR`.
* **Cosa contiene:** Il flusso di lavoro ordinario del sistema: avvio dei demoni, autenticazione con token CINECA, scaricamento e sincronizzazione delle aule, lettura dei feed news, operazioni svolte dal pannello `/admin` e messaggi diagnostici.

### B. `server_api_sys.log` (Log di Basso Livello / Watchdog Bash)
* **Percorso:** Generato nel percorso specificato in `~/.xinitrc`.
* **Gestione:** Generato dal ciclo watchdog di avvio grafico in `~/.xinitrc`:
  ```bash
  while true; do python3 $DIR_PROGETTO/server_api.py >> $DIR_PROGETTO/server_api_sys.log 2>&1; sleep 2; done &
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

Questi messaggi rappresentano la normale attività del chiosco a regime:

| Livello | Messaggio nel Log | Significato e Azione |
| :--- | :--- | :--- |
| **INFO** | `🚀 Avviato demone API CINECA (Modalità Admin Autenticata).` | Il thread di polling delle API CINECA è partito correttamente all'accensione del chiosco o al riavvio del processo. |
| **INFO** | `🚀 Avviato demone News (Footer).` | Il thread incaricato di scaricare i feed RSS e REST del nastro scorrevole è attivo. |
| **INFO** | `Avvio KioskServer HTTP sulla porta 8080` | Il server web HTTP locale è pronto e in ascolto per servire la dashboard (`remoto.html`) e le API locali. |
| **INFO** | `Avvio KioskServer HTTPS (SSL) sulla porta 8443` | Il server web cifrato HTTPS su thread parallelo è attivo e in ascolto. |
| **WARNING** | `⚠️ HTTPS abilitato ma file certificato o chiave non trovati (...). Server HTTPS non avviato.` | L'HTTPS è stato impostato su `true` in `config.yaml`, ma i file `.pem` o `.key` non sono presenti nel percorso specificato. Il sistema continua a funzionare regolarmente in HTTP. |
| **INFO** | `Richiesta di un nuovo Token a CINECA (Admin) in corso...` | Il demone sta contattando l'endpoint `/api/Utenti/login` di CINECA U-Planner per ottenere un token di sessione autenticato. |
| **INFO** | `✅ Login effettuato con successo. Nuovo token acquisito.` | Le credenziali tecniche fornite sono corrette e CINECA ha rilasciato un nuovo token valido. |
| **ERROR** | `❌ Errore di Login. Codice: 401. Risposta: ...` | CINECA ha respinto il login. Verificare username, password e clienteId (realm) in configurazione. |
| **ERROR** | `❌ Errore di rete durante il login: ...` | Il Raspberry Pi non è riuscito a raggiungere i server CINECA (assenza di rete, cavo scollegato, DNS non raggiungibile o interfaccia Wi-Fi occupata). |
| **ERROR** | `❌ Token scaduto o non valido (401). Forzo il rinnovo.` | Il token di sessione precedentemente rilasciato è scaduto. Il sistema lo invalida automaticamente e ripete il login al ciclo successivo. |
| **INFO** | `✅ Dati ricevuti! Trovati X impegni.` | Richiesta completata con successo: dopo aver filtrato per l'edificio impostato e scartato gli eventi non pertinenti, sono stati trovati `X` impegni validi per la giornata, pronti per essere mostrati a video. |
| **ERROR** | `❌ Errore HTTP 500/503: ...` | I server CINECA hanno risposto con un errore interno (es. manutenzione straordinaria dei server di Ateneo). Il chiosco manterrà a video l'ultimo stato valido salvato in `stato_impegni.json`. |
| **ERROR** | `❌ Errore critico nel ciclo API: ...` | Errore transitorio non fatale durante il ciclo di recupero. Il thread non si interrompe e riproverà dopo l'intervallo configurato. |
| **ERROR** | `⚠️ Errore recupero news da [Nome] ([URL]): ...` | Uno specifico feed RSS o endpoint REST delle news non risponde o ha restituito dati corrotti. Il sistema ignora la singola fonte e prosegue con le altre. |
| **ERROR** | `❌ Errore critico demone News: ...` | Errore generale nel thread del footer; viene intercettato senza causare il crash del server. |
| **ERROR** | `Errore lettura locandine: ...` | Impossibile leggere il contenuto della cartella `/locandine/` sul disco locale (es. permessi di lettura mancanti). |
| **INFO** | `Riavvio richiesto dall'Admin. Termino il processo (il watchdog Bash lo riavvierà).` | Dal pannello web `/admin` è stato cliccato il pulsante "Salva e Riavvia". Il processo Python termina regolarmente con codice 0 e lo script Bash `~/.xinitrc` lo riavvia entro 2 secondi. |
| **ERROR** | `Errore critico avvio server HTTP: ...` | Impossibile avviare il server web (es. la porta 8080 è già impegnata da un altro servizio o si è tentato di usare la porta 80 senza privilegi di root). |

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
| `ConnectionResetError: [Errno 104] Connection reset by peer`<br>`BrokenPipeError: [Errno 32] Broken pipe` | Uno scanner bot esterno su internet o un client ha aperto la connessione TCP e l'ha interrotta bruscamente prima della ricezione dei dati. | **Risolto nativamente nel codice:** il server è ora multi-thread (`KioskHTTPServer`) e la gestione errori (`handle_error`) intercetta e scarta silenziosamente le disconnessioni premature dei client, evitando che sporchino il log o blocchino il server. |
| `ModuleNotFoundError: No module named 'yaml'` (oppure `'requests'`) | Python è stato avviato senza le dipendenze necessarie installate a livello di sistema. | Eseguire su Raspberry: <br>`sudo apt install python3-requests python3-yaml` |
| `SyntaxError: invalid syntax` / `IndentationError` | File `server_api.py` corrotto o modificato con interruzioni di riga Windows (`CRLF`). | Eseguire su Raspberry: <br>`sudo apt install dos2unix && dos2unix server_api.py` |
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
