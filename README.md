# Kiosk4Uplanner - Dashboard Kiosk Informativa

*Sviluppato per l'Università di Pavia (UNIPV)*

**Versione:** 3.0 | **Autore:** [Vincenzo Oriti](https://oriti.net) ([vincenzo.oriti@unipv.it](mailto:vincenzo.oriti@unipv.it)) | **Progetto:** [GitHub](https://github.com/VOriti/Kiosk4Uplanner) | **Licenza:** [CC BY-NC-SA 4.0](LICENSE.txt) ([Testo completo](https://creativecommons.org/licenses/by-nc-sa/4.0/))

---

Questo progetto trasforma un Raspberry Pi in una postazione **Kiosk informativa**, da installare negli atri di un polo universitario per mostrare a studenti e docenti lo stato di occupazione delle aule in tempo reale.

Ha principalmente tre funzioni:
- mostra **l'occupazione in tempo reale delle aule** del palazzo;
- ogni tot minuti **mostra eventuali locandine di eventi in corso o futuri**;
- **rende disponibili i dati su una pagina web all'interno della rete locale**. In questo modo, il personale può controllare l'occupazione corrente delle aule direttamente dal browser del proprio PC o Smartphone.

Il repository è diviso in **due versioni** indipendenti, per adattarsi ai livelli di accesso a disposizione della struttura:

* 📖 [**Versione 1: Scraping DOM (Senza API)**](Versione%201%20-%20Scraping%20DOM%20(Senza%20API)/README.md) - Soluzione fai-da-te. Intercetta l'interfaccia web originale iniettando codice tramite Chromium. Consigliata solo se non disponi di alcuna credenziale di accesso a CINECA. Ideale se *non* si dispone di un'utenza API CINECA. *Necessita di un calendario pubblico da aprire per fare lo scraping dei dati.*

* 🚀 [**Versione 2: REST API CINECA (Consigliata)**](Versione%202%20-%20REST%20API%20CINECA%20(Consigliata)/README.md) - Metodo 'Native'. Interroga direttamente il DB di CINECA. Scelta consigliata per stabilità e prestazioni. Include persistenza degli annullamenti, mappatura dinamica degli edifici e un layout Responsive con menù interattivo. *Necessita delle credenziali di accesso a U-Planner.*

## Quale versione scegliere?

| Funzionalità | Versione 1 (Scraping) | Versione 2 (REST API - Consigliata) |
| :--- | :--- | :--- |
| **Metodo** | Iniezione DOM (Chromium) | Chiamata nativa REST API |
| **Credenziali** | **Nessuna richiesta** | Richiede Account U-Planner |
| **Stabilità** | Bassa (dipende dal layout web) | Alta (protocollo JSON) |
| **Persistenza** | No (stato volatile) | **Sì (salvataggio locale e tag "annullato/spostato" per modifiche live)** |
| **Risorse Hardware** | Elevato (Chrome è pesante) | **Minimo (Python Script)** |
| **Interfaccia Utente (UI)** | Fissa a due colonne (Desktop) | **Responsive Mobile & Desktop, Info Badge (Menu fluttuante)** |
| **Configurazione UI** | Modifica nel codice JS/HTML | **Blocco CONFIG_APP semplificato in remoto.html** |
| **Stato del Progetto** | Legacy (Backup) | **Produzione (Standard)** |
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