let CONFIG_APP = {};
let configCaricataDaServer = false;

async function fetchConfigPubblica() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 6000);
        const response = await fetch('./config_pubblica', { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!response.ok) throw new Error("Errore config_pubblica");
        const newConfig = await response.json();
        if (configCaricataDaServer && Object.keys(CONFIG_APP).length > 0 && JSON.stringify(CONFIG_APP) !== JSON.stringify(newConfig)) {
            window.location.reload();
            return;
        }
        CONFIG_APP = newConfig;
        configCaricataDaServer = true;
    } catch (e) {
        console.warn("Impossibile caricare configurazione, utilizzo fallback:", e);
        if (!configCaricataDaServer) {
            CONFIG_APP = {
                titoloSede: "Impegni Aule",
                urlLogo: "./logo.png",
                intervalloAggiornamento: 15000,
                messaggioNessunaLezione: "Nessun impegno programmato.",
                messaggioErroreRete: "Connessione persa col Server API. Tentativo di riconnessione...",
                pausaTraCaroselli: 180000,
                esposizioneLocandina: 10000,
                quotaCarosello: 0.30,
                mostraStatoPC: true,
                caroselloAttivo: true
            };
        }
    }
}

let tickerInterval;
let fetchNewsInterval;
let notizieCorrenti = [];
let indexVerticale = 0;
let newsPreferences = JSON.parse(localStorage.getItem('newsPreferences') || '{}');

async function aggiornaNews() {
    if (!CONFIG_APP.footer_news || !CONFIG_APP.footer_news.abilitato) {
        document.getElementById('kiosk-footer').style.display = 'none';
        return;
    }

    document.getElementById('kiosk-footer').style.display = 'flex';
    if (CONFIG_APP.footer_news.colore_sfondo) {
        document.getElementById('kiosk-footer').style.backgroundColor = CONFIG_APP.footer_news.colore_sfondo;
    }
    const hubBtn = document.getElementById('settings-hub-btn') || document.getElementById('news-hub-btn');
    if (hubBtn) {
        if (CONFIG_APP.footer_news.colore_btn) {
            hubBtn.style.backgroundColor = CONFIG_APP.footer_news.colore_btn;
        } else {
            hubBtn.style.backgroundColor = 'rgba(255,255,255,0.1)';
        }
    }

    const alertBox = document.getElementById('alert-box');
    if (CONFIG_APP.footer_news.alert_fisso_attivo && CONFIG_APP.footer_news.alert_testo) {
        alertBox.innerText = CONFIG_APP.footer_news.alert_testo;
        alertBox.style.display = 'flex';
    } else {
        alertBox.style.display = 'none';
    }

    try {
        const res = await fetch('./api/news');
        if (res.ok) {
            notizieCorrenti = await res.json();
            renderTicker();
        }
    } catch (e) {
        console.error("Errore recupero news:", e);
    }
}

function escapeHTML(valore) {
    return String(valore ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function formattaTitoloNews(titolo) {
    if (!titolo) return '';
    // DOMParser non esegue script né carica immagini: decodifica le entità in testo puro
    return (new DOMParser().parseFromString(String(titolo), 'text/html').body.textContent || '').trim();
}

function notiziaCorrisponde(notizia, query) {
    const q = String(query || '').trim().toLowerCase();
    return !q || String(notizia.titolo || '').toLowerCase().includes(q) || String(notizia.fonte || '').toLowerCase().includes(q);
}

function sanitizzaUrlLink(url) {
    if (!url) return '';
    const u = String(url).trim();
    if (u.startsWith('http://') || u.startsWith('https://')) {
        return encodeURI(u);
    }
    return '';
}

function renderTicker() {
    const wrapper = document.getElementById('ticker-wrapper');
    clearInterval(tickerInterval);

    const notizieFiltrate = notizieCorrenti.filter(n => {
        if (newsPreferences[n.fonte] !== undefined) {
            return newsPreferences[n.fonte];
        }
        return n.visibile !== false;
    });

    if (notizieFiltrate.length === 0) {
        wrapper.innerHTML = '';
        return;
    }

    const stile = CONFIG_APP.footer_news.stile_scorrimento || 'orizzontale';
    const colTesto = CONFIG_APP.footer_news.colore_testo || '#c9d1d9';
    const dimTesto = CONFIG_APP.footer_news.dimensione_testo || '1.15rem';

    if (stile === 'orizzontale') {
        const testi = notizieFiltrate.map(n => {
            const titPulito = formattaTitoloNews(n.titolo);
            const safeLink = sanitizzaUrlLink(n.link);
            const testoInterno = `<strong>[${escapeHTML(n.fonte)}]</strong> ${escapeHTML(titPulito)}`;
            return safeLink ? `<a href="${escapeHTML(safeLink)}" target="_blank" rel="noopener noreferrer" class="ticker-link">${testoInterno}</a>` : testoInterno;
        });
        const stringaUnica = testi.join(' &nbsp;&nbsp;&bull;&nbsp;&nbsp; ');

        const velocitaBase = CONFIG_APP.footer_news.velocita || 50;
        const durata = Math.max(10, (stringaUnica.length / 5) * (velocitaBase / 50));

        wrapper.innerHTML = `<span class="ticker-orizzontale">${stringaUnica}</span>`;
        const spanOrizz = wrapper.querySelector('.ticker-orizzontale');
        if (spanOrizz) {
            spanOrizz.style.animationDuration = durata + 's';
            spanOrizz.style.color = colTesto;
            spanOrizz.style.fontSize = dimTesto;
        }
    } else {
        wrapper.innerHTML = '<div id="ticker-verticale" class="ticker-verticale"></div>';
        const divVert = document.getElementById('ticker-verticale');
        divVert.style.color = colTesto;
        divVert.style.fontSize = dimTesto;
        indexVerticale = 0;

        const mostraProssima = () => {
            divVert.style.opacity = 0;
            setTimeout(() => {
                const n = notizieFiltrate[indexVerticale];
                const titPulito = formattaTitoloNews(n.titolo);
                const safeLink = sanitizzaUrlLink(n.link);
                const testoInterno = `<strong>[${escapeHTML(n.fonte)}]</strong> ${escapeHTML(titPulito)}`;
                const htmlContenuto = safeLink ? `<a href="${escapeHTML(safeLink)}" target="_blank" rel="noopener noreferrer" class="ticker-link">${testoInterno}</a>` : testoInterno;
                divVert.innerHTML = `<span class="ticker-verticale-inner">${htmlContenuto}</span>`;
                divVert.style.opacity = 1;
                indexVerticale = (indexVerticale + 1) % notizieFiltrate.length;
            }, 500);
        };

        mostraProssima();
        tickerInterval = setInterval(mostraProssima, 6000);
    }
}

function generaCardHTML(impegno) {
    let classeStato = impegno.inCorso ? 'in-corso' : '';
    if (impegno.cancellato) classeStato += ' cancellato';

    let htmlAvviso = '';
    if (impegno.avviso) {
        const classeBadge = impegno.cancellato ? 'badge-rosso' : 'badge-giallo';
        htmlAvviso = `<div class="badge-avviso ${classeBadge}">${escapeHTML(impegno.avviso)}</div>`;
    }

    const stileTesto = impegno.cancellato ? 'testo-barrato' : '';
    let iconaStato = '';
    if (CONFIG_APP.mostraStatoPC) {
        if (impegno.stato_cineca === 'P') {
            iconaStato = `<span class="badge-stato stato-p">P</span>`;
        } else if (impegno.stato_cineca === 'C') {
            iconaStato = `<span class="badge-stato stato-c">C</span>`;
        }
    }

    return `
        <div class="card ${classeStato}">
            ${htmlAvviso}
            <div class="card-header">
                <div class="titolo ${stileTesto}">${iconaStato}${escapeHTML(impegno.titolo)}</div>
                <div class="aula ${stileTesto}">${escapeHTML(impegno.aula)}</div>
            </div>
            <div class="card-footer">
                <div class="docente ${stileTesto}">${escapeHTML(impegno.docente)}</div>
                <div class="orario ${stileTesto}">${escapeHTML(impegno.orario)}</div>
            </div>
        </div>
    `;
}

let eraOffline = false;
let erroriConsecutivi = 0;
let datiCaricatiAlmenoUnaVolta = false;
let ultimoDatiJson = null;
let offsetOrologio = 0;   // secondi da sommare all'ora del browser per allinearsi al server
let ultimoStato = null;
let oraUltimoDatiOk = null;

function classificaImpegni(dati, adessoSec) {
    const inCorso = [], futuri = [];
    for (const imp of dati) {
        if (imp.timestamp_fine < adessoSec) continue;
        const copia = Object.assign({}, imp, { inCorso: imp.timestamp_inizio <= adessoSec });
        (copia.inCorso ? inCorso : futuri).push(copia);
    }
    futuri.sort((a, b) => a.timestamp_inizio - b.timestamp_inizio);
    return { inCorso, futuri };
}

function valutaFreschezza(stato, adessoSec) {
    const soglia = Math.max(900, 3 * (stato.intervallo_sec || 300));
    if (stato.ultimo_sync_cineca == null) {
        return adessoSec - stato.avvio_server > 600
            ? { mostra: true, testo: '⚠️ In attesa di dati da U-Planner' } : { mostra: false, testo: '' };
    }
    if (adessoSec - stato.ultimo_sync_cineca <= soglia) return { mostra: false, testo: '' };
    const ora = new Date(stato.ultimo_sync_cineca * 1000).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    return { mostra: true, testo: `⚠️ Dati aggiornati alle ${ora}` };
}

function aggiornaBadgeFreschezza() {
    const badge = document.getElementById('badge-freschezza');
    if (!badge) return;

    if (erroriConsecutivi >= 3 && datiCaricatiAlmenoUnaVolta) {
        const ora = oraUltimoDatiOk || (ultimoStato && ultimoStato.ultimo_sync_cineca ? new Date(ultimoStato.ultimo_sync_cineca * 1000).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }) : '--:--');
        badge.textContent = `🔴 OFFLINE — dati delle ${ora}`;
        badge.className = 'badge-offline';
        badge.removeAttribute('hidden');
        return;
    }

    if (!ultimoStato) {
        badge.textContent = '';
        badge.setAttribute('hidden', '');
        return;
    }

    const adessoSec = (Date.now() / 1000) + offsetOrologio;
    const f = valutaFreschezza(ultimoStato, adessoSec);
    if (f.mostra) {
        badge.textContent = f.testo;
        badge.className = 'badge-avviso';
        badge.removeAttribute('hidden');
    } else {
        badge.textContent = '';
        badge.setAttribute('hidden', '');
    }
}

async function aggiornaStato() {
    try {
        const risposta = await fetch('./stato');
        if (!risposta.ok) return;
        const stato = await risposta.json();
        ultimoStato = stato;
        offsetOrologio = stato.ora_server - (Date.now() / 1000);
        aggiornaBadgeFreschezza();
    } catch (e) {
        console.warn("Errore aggiornaStato:", e);
    }
}

async function scaricaDatiServerLocale() {
    const dashboard = document.getElementById('dashboard');
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 6000);
        const risposta = await fetch('./dati.json', { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!risposta.ok) throw new Error('Errore HTTP ' + risposta.status);
        const datiAule = await risposta.json();

        erroriConsecutivi = 0;
        eraOffline = false;
        datiCaricatiAlmenoUnaVolta = true;
        oraUltimoDatiOk = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
        aggiornaBadgeFreschezza();

        const eraStatoSistema = !document.getElementById('colonna-in-corso');

        if (!datiAule || datiAule.length === 0) {
            const emptyJson = JSON.stringify(datiAule || []);
            if (!eraStatoSistema || emptyJson !== ultimoDatiJson) {
                ultimoDatiJson = emptyJson;
                dashboard.innerHTML = `<div class="stato-sistema">${escapeHTML(CONFIG_APP.messaggioNessunaLezione)}</div>`;
            }
            return;
        }

        const adessoSec = (Date.now() / 1000) + offsetOrologio;
        const { inCorso, futuri } = classificaImpegni(datiAule, adessoSec);
        const datiClassificati = { inCorso, futuri };
        const datiJsonStr = JSON.stringify(datiClassificati);

        const colInCorso = document.getElementById('colonna-in-corso');
        const colFuturi = document.getElementById('colonna-futuri');
        const layoutPresente = colInCorso && colFuturi;

        // Se la struttura delle colonne è già presente e i dati non sono cambiati, non tocchiamo il DOM
        if (layoutPresente && datiJsonStr === ultimoDatiJson) {
            return;
        }
        ultimoDatiJson = datiJsonStr;

        let htmlInCorso = '', htmlFuturi = '';
        inCorso.forEach(imp => {
            htmlInCorso += generaCardHTML(imp);
        });
        futuri.forEach(imp => {
            htmlFuturi += generaCardHTML(imp);
        });

        if (!htmlInCorso) htmlInCorso = '<div class="colonna-vuota">Nessuna lezione in questo momento</div>';
        if (!htmlFuturi) htmlFuturi = '<div class="colonna-vuota">Nessuna lezione programmata</div>';

        if (layoutPresente) {
            const scrollInCorso = colInCorso.scrollTop;
            const scrollFuturi = colFuturi.scrollTop;

            colInCorso.innerHTML = htmlInCorso;
            colFuturi.innerHTML = htmlFuturi;

            colInCorso.scrollTop = scrollInCorso;
            colFuturi.scrollTop = scrollFuturi;
        } else {
            dashboard.innerHTML = `
                <div class="layout-colonne">
                    <div class="colonna-sezione">
                        <h2 class="titolo-colonna">In Corso</h2>
                        <div id="colonna-in-corso" class="colonna-scroll">
                            ${htmlInCorso}
                        </div>
                    </div>
                    <div class="colonna-sezione">
                        <h2 class="titolo-colonna">Prossimi Eventi</h2>
                        <div id="colonna-futuri" class="colonna-scroll">
                            ${htmlFuturi}
                        </div>
                    </div>
                </div>
            `;
        }
    } catch (errore) {
        erroriConsecutivi++;
        console.warn("Errore scaricaDatiServerLocale:", errore);
        aggiornaBadgeFreschezza();
        // Non cancellare la schermata se abbiamo già dati visualizzati e l'errore è transitorio
        if (!datiCaricatiAlmenoUnaVolta) {
            eraOffline = true;
            ultimoDatiJson = null;
            dashboard.innerHTML = `
                <div class="stato-sistema offline">
                    <svg class="offline-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                    <br>${escapeHTML(CONFIG_APP.messaggioErroreRete)}
                </div>
            `;
        }
    }
}

function urlLocandina(nome) {
    // Nomi immutabili: nessun cache-busting. %27 evita la rottura di url('...').
    return './locandine/' + encodeURIComponent(nome).replace(/'/g, '%27');
}

const QUOTA_MAX_CAROSELLO = 0.30;
const DURATA_TRANSIZIONE_MS = 1550;   // 50 ms di comparsa + 1500 ms di dissolvenza
const INATTIVITA_KIOSK_MS = 60000;

function calcolaGruppiPerCiclo(pausaMs, esposizioneMs, quota, transizioneMs) {
    const budget = pausaMs * quota / (1 - quota);
    return Math.max(1, Math.floor(budget / (esposizioneMs + transizioneMs)));
}

function selezionaGruppi(gruppi, inizio, quanti) {
    if (gruppi.length <= quanti) return { selezionati: gruppi, prossimoInizio: 0 };
    const selezionati = [];
    for (let i = 0; i < quanti; i++) selezionati.push(gruppi[(inizio + i) % gruppi.length]);
    return { selezionati, prossimoInizio: (inizio + quanti) % gruppi.length };
}

let indiceRotazione = 0;
let interrompiCarosello = null;

function attendiCarosello(ms) {
    return new Promise(resolve => {
        let timer = null;
        const pulisci = () => {
            if (timer) {
                clearTimeout(timer);
                timer = null;
            }
            if (interrompiCarosello === onInterrompi) {
                interrompiCarosello = null;
            }
        };
        const onInterrompi = () => {
            pulisci();
            resolve('interrotto');
        };
        interrompiCarosello = onInterrompi;
        timer = setTimeout(() => {
            pulisci();
            resolve('completato');
        }, ms);
    });
}

const advOverlay = document.getElementById('kiosk-adv');
if (advOverlay) {
    advOverlay.addEventListener('pointerdown', () => interrompiCarosello && interrompiCarosello());
    advOverlay.addEventListener('click', () => interrompiCarosello && interrompiCarosello());
}
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && interrompiCarosello) {
        interrompiCarosello();
    }
});

async function riproduciLocandine() {
    if (!isLocandineActiveOnDevice()) return;

    const isLandscape = window.innerWidth > window.innerHeight;
    let immaginiValide = [];

    try {
        const res = await fetch('./lista_locandine.json');
        if (res.ok) {
            const files = await res.json();
            for (let f of files) {
                const url = urlLocandina(f);
                const valid = await new Promise(resolve => {
                    let img = new Image(); img.onload = () => resolve(url); img.onerror = () => resolve(null); img.src = url;
                });
                if (valid) immaginiValide.push(valid);
            }
        }
    } catch (e) {
        console.error("Errore fetch locandine", e);
    }

    if (immaginiValide.length === 0) return;

    const gruppi = [];
    const imgPerGruppo = isLandscape ? 2 : 1;
    for (let i = 0; i < immaginiValide.length; i += imgPerGruppo) {
        gruppi.push(immaginiValide.slice(i, i + imgPerGruppo));
    }

    const pausa = CONFIG_APP.pausaTraCaroselli || 180000;
    const esposizione = CONFIG_APP.esposizioneLocandina || 10000;
    const quotaEffettiva = (typeof CONFIG_APP.quotaCarosello === 'number' && CONFIG_APP.quotaCarosello >= 0.10 && CONFIG_APP.quotaCarosello <= 0.50) ? CONFIG_APP.quotaCarosello : QUOTA_MAX_CAROSELLO;
    const quanti = calcolaGruppiPerCiclo(pausa, esposizione, quotaEffettiva, DURATA_TRANSIZIONE_MS);
    const rotazione = selezionaGruppi(gruppi, indiceRotazione, quanti);
    indiceRotazione = rotazione.prossimoInizio;
    const gruppiDaMostrare = rotazione.selezionati;

    try {
        advOverlay.style.display = 'flex';
        for (let i = 0; i < gruppiDaMostrare.length; i++) {
            advOverlay.innerHTML = '';
            for (const src of gruppiDaMostrare[i]) {
                const slide = document.createElement('div');
                slide.className = 'adv-slide';
                slide.style.backgroundImage = "url('" + src + "')";
                advOverlay.appendChild(slide);
            }
            if (await attendiCarosello(50) === 'interrotto') break;
            advOverlay.style.opacity = '1';
            if (await attendiCarosello(esposizione) === 'interrotto') break;
            advOverlay.style.opacity = '0';
            if (await attendiCarosello(1500) === 'interrotto') break;
        }
    } finally {
        interrompiCarosello = null;
        advOverlay.style.display = 'none';
        advOverlay.innerHTML = '';
        advOverlay.style.opacity = '0';
    }
}

function pianificaCarosello() {
    setTimeout(async () => {
        await riproduciLocandine();
        pianificaCarosello();
    }, CONFIG_APP.pausaTraCaroselli || 180000);
}

let timerInattivitaKiosk = null;

function chiudiInterfacciaKiosk() {
    closeNewsHub();
    const badge = document.getElementById('info-badge');
    if (badge) {
        badge.classList.remove('aperto');
    }
}

function riarmaInattivita() {
    if (timerInattivitaKiosk) {
        clearTimeout(timerInattivitaKiosk);
    }
    timerInattivitaKiosk = setTimeout(chiudiInterfacciaKiosk, INATTIVITA_KIOSK_MS);
}

function attivaModalitaKiosk() {
    document.body.classList.add('modalita-kiosk');
    ['pointerdown', 'keydown'].forEach(evt => {
        document.addEventListener(evt, riarmaInattivita, { passive: true });
    });
    riarmaInattivita();
}

function collegaEventiInterfaccia() {
    const settingsBtn = document.getElementById('settings-hub-btn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', openSettingsHub);
    }

    const newsModal = document.getElementById('news-hub-modal');
    if (newsModal) {
        newsModal.addEventListener('click', (event) => {
            if (event.target === newsModal) closeNewsHub();
        });
    }

    const closeBtn = document.getElementById('close-news-hub-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeNewsHub);
    }

    const toggleLoc = document.getElementById('pref_toggle_locandine');
    if (toggleLoc) {
        toggleLoc.addEventListener('change', (event) => {
            toggleLocandinePreference(event.target.checked);
        });
    }

    const newsSearch = document.getElementById('news-search');
    if (newsSearch) {
        newsSearch.addEventListener('input', onNewsSearchInput);
    }

    const thData = document.getElementById('th-sort-data');
    if (thData) thData.addEventListener('click', () => sortNewsTable('data'));
    const thFonte = document.getElementById('th-sort-fonte');
    if (thFonte) thFonte.addEventListener('click', () => sortNewsTable('fonte'));
    const thTitolo = document.getElementById('th-sort-titolo');
    if (thTitolo) thTitolo.addEventListener('click', () => sortNewsTable('titolo'));
}

document.addEventListener('DOMContentLoaded', async () => {
    collegaEventiInterfaccia();

    if (isKioskEnvironment()) {
        attivaModalitaKiosk();
    }

    await fetchConfigPubblica();

    document.getElementById('titolo-sede').innerText = CONFIG_APP.titoloSede || "Impegni Aule";
    document.title = "Dashboard - " + (CONFIG_APP.titoloSede || "Impegni Aule");
    if (CONFIG_APP.urlLogo && CONFIG_APP.urlLogo !== "") {
        document.getElementById('logo-sede').src = CONFIG_APP.urlLogo;
        document.getElementById('banner-wrapper').style.display = 'block';
    }

    document.getElementById('link-calendario').href = CONFIG_APP.urlCalendario || "#";
    document.getElementById('link-repo').href = CONFIG_APP.urlRepo || "#";
    document.getElementById('link-licenza').href = CONFIG_APP.urlLicenza || "#";
    document.getElementById('nome-autore').innerText = CONFIG_APP.autore || "Autore";
    const testoInformativo = "Per suggerimenti, richieste di modifica o segnalazione di malfunzionamenti: ";
    document.getElementById('link-autore').setAttribute('data-tooltip', testoInformativo + (CONFIG_APP.emailAutore || ""));

    document.querySelector('.badge-icona').addEventListener('click', function () {
        document.getElementById('info-badge').classList.toggle('aperto');
    });

    // Inizializza lo stato delle locandine per il dispositivo
    isLocandineActiveOnDevice();

    setInterval(() => {
        document.getElementById('orologio').innerText = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
        aggiornaBadgeFreschezza();
    }, 1000);

    aggiornaStato();
    setInterval(aggiornaStato, 30000);

    scaricaDatiServerLocale();
    setInterval(scaricaDatiServerLocale, CONFIG_APP.intervalloAggiornamento || 5000);

    setInterval(fetchConfigPubblica, 15000);

    aggiornaNews();
    fetchNewsInterval = setInterval(aggiornaNews, 15 * 60 * 1000);

    // Regola dinamicamente il margine della dashboard in base all'altezza del footer
    const footerObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            if (entry.target.style.display !== 'none') {
                document.getElementById('dashboard').style.marginBottom = entry.borderBoxSize[0].blockSize + 'px';
            } else {
                document.getElementById('dashboard').style.marginBottom = '0';
            }
        }
    });
    footerObserver.observe(document.getElementById('kiosk-footer'));

    if (CONFIG_APP.caroselloAttivo === true) {
        pianificaCarosello();
    } else {
        console.log("Carosello disattivato da configurazione.");
    }
});

function isKioskEnvironment() {
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const params = new URLSearchParams(window.location.search);
    const isKioskFlag = params.has('kiosk') && params.get('kiosk') !== 'false' && params.get('kiosk') !== '0';
    return isLocalhost || isKioskFlag;
}

function isLocandineActiveOnDevice() {
    if (CONFIG_APP.caroselloAttivo === false) {
        return false;
    }
    if (isKioskEnvironment()) {
        return true;
    }
    const savedPref = localStorage.getItem('disabilita_locandine');
    if (savedPref !== null) {
        return savedPref !== 'true';
    }
    return false;
}

function toggleLocandinePreference(attivo) {
    if (isKioskEnvironment()) return;
    localStorage.setItem('disabilita_locandine', attivo ? 'false' : 'true');
    aggiornaUILocandineModal();
}

function aggiornaUILocandineModal() {
    const isGlobalActive = CONFIG_APP.caroselloAttivo !== false;
    const toggleEl = document.getElementById('pref_toggle_locandine');
    const badgeEl = document.getElementById('locandine-badge-stato');
    const noticeEl = document.getElementById('locandine-disabled-notice');
    const containerEl = document.getElementById('locandine-control-container');

    if (!toggleEl || !badgeEl) return;

    if (!isGlobalActive) {
        toggleEl.checked = false;
        toggleEl.disabled = true;
        if (containerEl) {
            containerEl.style.opacity = '0.5';
            containerEl.style.pointerEvents = 'none';
        }
        badgeEl.innerText = 'DISATTIVATE DALL\'ADMIN';
        badgeEl.style.background = '#6e7681';
        if (noticeEl) noticeEl.style.display = 'block';
    } else {
        toggleEl.disabled = false;
        if (containerEl) {
            containerEl.style.opacity = '1';
            containerEl.style.pointerEvents = 'auto';
        }
        if (noticeEl) noticeEl.style.display = 'none';

        const isActive = isLocandineActiveOnDevice();
        toggleEl.checked = isActive;
        if (isActive) {
            badgeEl.innerText = 'ATTIVE';
            badgeEl.style.background = '#238636';
        } else {
            badgeEl.innerText = 'DISATTIVATE';
            badgeEl.style.background = '#da3633';
        }
    }
}

function openSettingsHub() {
    document.getElementById('news-hub-modal').style.display = 'flex';
    aggiornaUILocandineModal();

    const fontiInfo = {};
    if (CONFIG_APP.footer_news && Array.isArray(CONFIG_APP.footer_news.fonti)) {
        CONFIG_APP.footer_news.fonti.forEach(f => {
            if (f && f.nome && f.nome.trim() !== '' && f.abilitata !== false) {
                fontiInfo[f.nome.trim()] = f.visibile_di_default !== false;
            }
        });
    }
    notizieCorrenti.forEach(n => {
        if (n && n.fonte && fontiInfo[n.fonte] === undefined) {
            fontiInfo[n.fonte] = n.visibile !== false;
        }
    });

    const filterContainer = document.getElementById('news-filters-container');
    if (filterContainer) {
        filterContainer.innerHTML = '';
        Object.keys(fontiInfo).forEach(fonte => {
            let isChecked = false;
            if (newsPreferences[fonte] !== undefined) {
                isChecked = newsPreferences[fonte];
            } else {
                isChecked = fontiInfo[fonte];
            }

            const conteggio = notizieCorrenti.filter(n => n.fonte === fonte).length;

            const item = document.createElement('label');
            item.className = 'news-source-item';

            const spanLabel = document.createElement('span');
            spanLabel.className = 'news-source-label';
            spanLabel.textContent = fonte + ' (' + conteggio + ')';

            const switchSpan = document.createElement('span');
            switchSpan.className = 'switch';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = isChecked;
            input.addEventListener('change', () => {
                toggleNewsSource(fonte, input.checked);
            });

            const slider = document.createElement('span');
            slider.className = 'slider';

            switchSpan.appendChild(input);
            switchSpan.appendChild(slider);
            item.appendChild(spanLabel);
            item.appendChild(switchSpan);
            filterContainer.appendChild(item);
        });
    }

    const searchInput = document.getElementById('news-search');
    if (searchInput) searchInput.value = '';

    renderNewsTable();
}

function openNewsHub() {
    openSettingsHub();
}

function closeNewsHub() {
    document.getElementById('news-hub-modal').style.display = 'none';
}

function toggleNewsSource(fonte, isChecked) {
    newsPreferences[fonte] = isChecked;
    localStorage.setItem('newsPreferences', JSON.stringify(newsPreferences));
    renderTicker();
}

let currentSortCol = null;
let currentSortDir = 1;

function sortNewsTable(col) {
    if (currentSortCol === col) {
        currentSortDir *= -1;
    } else {
        currentSortCol = col;
        currentSortDir = 1;
    }

    // Aggiorna icone freccia
    const headers = {
        'data': 'Data',
        'fonte': 'Fonte',
        'titolo': 'Titolo'
    };
    Object.keys(headers).forEach(k => {
        const el = document.getElementById(`th-sort-${k}`);
        if (el) {
            if (k === col) {
                el.innerText = headers[k] + (currentSortDir === 1 ? ' ▲' : ' ▼');
            } else {
                el.innerText = headers[k] + ' ↕';
            }
        }
    });

    notizieCorrenti.sort((a, b) => {
        if (col === 'data') {
            const toTs = (s) => {
                if (!s || s === '-') return 0;
                const parts = s.split('/');
                if (parts.length === 3) return new Date(parts[2], parts[1] - 1, parts[0]).getTime();
                const parsed = Date.parse(s);
                return isNaN(parsed) ? 0 : parsed;
            };
            return (toTs(a.data) - toTs(b.data)) * currentSortDir;
        }
        let valA = a[col] || '';
        let valB = b[col] || '';
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return -1 * currentSortDir;
        if (valA > valB) return 1 * currentSortDir;
        return 0;
    });
    renderNewsTable();
}

let searchDebounceTimeout = null;
function onNewsSearchInput() {
    clearTimeout(searchDebounceTimeout);
    searchDebounceTimeout = setTimeout(() => {
        renderNewsTable();
    }, 150);
}

function renderNewsTable() {
    const searchInput = document.getElementById('news-search');
    const query = searchInput ? searchInput.value : '';
    const tbody = document.getElementById('news-table-body');
    tbody.innerHTML = '';
    notizieCorrenti.forEach(n => {
        if (!notiziaCorrisponde(n, query)) return;
        const tr = document.createElement('tr');
        tr.className = 'news-row';
        const titPulito = formattaTitoloNews(n.titolo);
        const safeLink = sanitizzaUrlLink(n.link);
        const link = safeLink ? `<a href="${escapeHTML(safeLink)}" target="_blank" rel="noopener noreferrer" class="news-title-link">${escapeHTML(titPulito)}</a>` : escapeHTML(titPulito);
        tr.innerHTML = `
            <td class="news-cell news-cell-date">${escapeHTML(n.data || '-')}</td>
            <td class="news-cell"><span class="news-source-badge">${escapeHTML(n.fonte)}</span></td>
            <td class="news-cell">${link}</td>
        `;
        tbody.appendChild(tr);
    });
}
