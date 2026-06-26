/**
 * Kiosk4Uplanner - DASHBOARD KIOSK INFORMATIVA
 * Kindly developed for University of Pavia (UNIPV)
 * -----------------------------------------------------
 * Una soluzione per trasformare un Raspberry Pi in una postazione
 * Kiosk per il monitoraggio aule in tempo reale.
 * -----------------------------------------------------
 * Nessuna dipendenza esterna richiesta per i client.
 * ----------------------------------------------------
 * Author Information / Informazioni sull'autore
 * @author  Vincenzo Oriti
 * @contact vincenzo.oriti@unipv.it
 * @personal_page https://oriti.net
 * ---------------------------------------------------------
 * Project information / Informazioni sul progetto
 * @project_page https://github.com/VOriti/Kiosk4Uplanner
 * @version 1.0
 * @license CC BY-NC-SA 4.0
 * @license_url https://creativecommons.org/licenses/by-nc-sa/4.0/    
 */

// ============================================================================
// 1. CONFIGURAZIONE LOGICA
// ============================================================================
const CONFIG = {
    titoloDashboard: "Impegni Aule",
    formatoOrario24h: true,
    testiDaRimuovere: ["Palazzo San Felice", "San Felice"],
    serverLocaleUrl: "http://localhost:8080",
    cicloLetturaDati: 2000,
    pausaTraCaroselli: 180000,
    esposizioneLocandina: 15000,
    intervalloHardReset: 1800000  // 30 minuti
};

// ============================================================================
// 2. CONFIGURAZIONE GRAFICA (MONITOR KIOSK)
// Regola qui le grandezze per far stare pi� o meno eventi sul tuo 40"
// ============================================================================
const CONFIG_UI = {
    // Logo (lasciare stringa vuota '' per nasconderlo)
    urlLogo: 'http://localhost:8080/logo.png',

    // Palette Colori
    coloreSfondo: '#0d1117',
    coloreScheda: '#161b22',
    coloreTestoPrincipale: '#c9d1d9',
    coloreTestoSecondario: '#8b949e',
    accentoTitolo: '#58a6ff',
    accentoOrologio: '#f2cc60',
    bordoInCorso: '#238636',
    bordoFuturo: '#58a6ff',

    // Dimensioni e Spaziature (Ridotte per Kiosk ad alta densit�)
    dimensioneOrario: '1.5rem',  // Prima era 2rem
    dimensioneAula: '1.1rem',    // Prima era 1.6rem
    dimensioneTitolo: '1.4rem',  // Prima era 1.7rem
    dimensioneDocente: '1.1rem', // Prima era 1.3rem

    paddingScheda: '10px 15px',  // Spazio interno alle card (era 15px 20px)
    gapTraSchede: '10px'         // Spazio verticale tra una card e l'altra (era 15px)
};

console.log("?? CDP: Script Kiosk avviato. Caricamento configurazione...");

// INIEZIONE DINAMICA DEL CSS
if (!document.getElementById('kiosk-styles')) {
    const style = document.createElement('style');
    style.id = 'kiosk-styles';
    style.innerHTML = `
        :root {
            --bg-main: ${CONFIG_UI.coloreSfondo};
            --bg-card: ${CONFIG_UI.coloreScheda};
            --txt-main: ${CONFIG_UI.coloreTestoPrincipale};
            --txt-sec: ${CONFIG_UI.coloreTestoSecondario};
            --acc-titolo: ${CONFIG_UI.accentoTitolo};
            --acc-orologio: ${CONFIG_UI.accentoOrologio};
            --bordo-corso: ${CONFIG_UI.bordoInCorso};
            --bordo-futuro: ${CONFIG_UI.bordoFuturo};
        }
        #kiosk-overlay {
            position:fixed !important; top:0 !important; left:0 !important; width:100vw !important; height:100vh !important; 
            background-color:var(--bg-main) !important; z-index:2147483647 !important; overflow-y:hidden !important; 
            font-family: system-ui, sans-serif !important; color: var(--txt-main) !important; 
            padding: 20px 30px !important; box-sizing: border-box !important; display: flex !important; flex-direction: column !important;
        }
        .k-header {
            display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #30363d; 
            padding-bottom:10px; margin-bottom:20px; flex-shrink: 0;
        }
        .k-card {
            background: var(--bg-card); border-left: 6px solid var(--bordo-futuro); 
            padding: ${CONFIG_UI.paddingScheda}; border-radius: 6px; margin-bottom: ${CONFIG_UI.gapTraSchede}; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; flex-direction: column; gap: 6px;
        }
        .k-card.in-corso { border-left-color: var(--bordo-corso); }
        .k-card-top { display: flex; justify-content: space-between; align-items: center; }
        .k-orario { font-size: ${CONFIG_UI.dimensioneOrario}; font-weight: bold; color: var(--txt-main); }
        .k-aula { font-size: ${CONFIG_UI.dimensioneAula}; color: var(--acc-orologio); font-weight: bold; background: #21262d; padding: 3px 10px; border-radius: 15px; }
        .k-titolo { font-size: ${CONFIG_UI.dimensioneTitolo}; font-weight: 600; line-height: 1.1; color: #e6edf3; }
        .k-docente { font-size: ${CONFIG_UI.dimensioneDocente}; color: var(--txt-sec); }
        .k-col-title { font-size:1.6rem; color:var(--txt-sec); border-bottom:2px solid #30363d; padding-bottom:8px; margin-top:0; margin-bottom:15px; text-transform:uppercase; }
    `;
    document.head.appendChild(style);
}

// SISTEMA DI NOTIFICHE A SCOMPARSA (TOAST)
window.mostraNotifica = function (messaggio, tipo = 'info') {
    const coloreBordo = tipo === 'errore' ? '#da3633' : (tipo === 'successo' ? '#238636' : '#58a6ff');
    const icona = tipo === 'errore' ? '? ' : (tipo === 'successo' ? '? ' : '?? ');
    const notifica = document.createElement('div');
    notifica.style.cssText = `position:fixed !important; top:30px !important; right:30px !important; background-color:#161b22 !important; border-left:8px solid ${coloreBordo} !important; color:#c9d1d9 !important; padding:15px 25px !important; border-radius:8px !important; box-shadow:0 10px 25px rgba(0,0,0,0.6) !important; z-index:2147483649 !important; font-size:1.4rem !important; font-family:system-ui, sans-serif !important; font-weight:bold !important; opacity:0; transform:translateX(50px); transition:all 0.4s ease-out !important; pointer-events:none !important;`;
    notifica.innerText = icona + messaggio;
    document.body.appendChild(notifica);
    requestAnimationFrame(() => { notifica.style.opacity = '1'; notifica.style.transform = 'translateX(0)'; });
    setTimeout(() => {
        notifica.style.opacity = '0'; notifica.style.transform = 'translateX(50px)';
        setTimeout(() => notifica.remove(), 500);
    }, 5000);
};

// MOTORE DIGITAL SIGNAGE
if (!document.getElementById('kiosk-adv')) {
    const advOverlay = document.createElement('div');
    advOverlay.id = 'kiosk-adv';
    advOverlay.style.cssText = 'position:fixed !important; top:0 !important; left:0 !important; width:100vw !important; height:100vh !important; background-color:#000 !important; z-index:2147483648 !important; display:none; opacity:0; transition: opacity 1.5s ease-in-out !important; justify-content: center !important; align-items: center !important; gap: 40px !important; padding: 40px !important; box-sizing: border-box !important;';
    document.body.appendChild(advOverlay);

    async function riproduciLocandine() {
        const isLandscape = window.innerWidth > window.innerHeight;
        const immaginiValide = [];
        for (let i = 1; i <= 4; i++) {
            const url = `${CONFIG.serverLocaleUrl}/locandine/${i}.jpg?` + Date.now();
            const urlConfermata = await new Promise(resolve => {
                let img = new Image(); img.onload = () => resolve(url); img.onerror = () => resolve(null); img.src = url;
            });
            if (urlConfermata) immaginiValide.push(urlConfermata);
        }
        if (immaginiValide.length === 0) return;

        const gruppi = [];
        const immaginiPerGruppo = isLandscape ? 2 : 1;
        for (let i = 0; i < immaginiValide.length; i += immaginiPerGruppo) { gruppi.push(immaginiValide.slice(i, i + immaginiPerGruppo)); }

        advOverlay.style.display = 'flex';
        for (let i = 0; i < gruppi.length; i++) {
            advOverlay.innerHTML = gruppi[i].map(src => `<div style="flex:1; height:100%; width:100%; background-image:url('${src}'); background-size:contain; background-position:center; background-repeat:no-repeat;"></div>`).join('');
            await new Promise(r => setTimeout(r, 50));
            advOverlay.style.opacity = '1';
            await new Promise(r => setTimeout(r, CONFIG.esposizioneLocandina));
            advOverlay.style.opacity = '0';
            await new Promise(r => setTimeout(r, 1500));
        }
        advOverlay.style.display = 'none'; advOverlay.innerHTML = '';
    }
    setInterval(riproduciLocandine, CONFIG.pausaTraCaroselli);
}

// MOTORE DASHBOARD AULE
setInterval(() => {
    const calendario = document.querySelector('.fc-view-container');
    if (!calendario) return;

    const isLandscape = window.innerWidth > window.innerHeight;

    let overlay = document.getElementById('kiosk-overlay');
    if (!overlay) {
        overlay = document.createElement('div'); overlay.id = 'kiosk-overlay';

        // Il banner occupa il 100% della larghezza e ha gli angoli morbidamente smussati
        const htmlLogo = CONFIG_UI.urlLogo ? `<div style="width:100%; text-align:center; margin-bottom:20px;"><img src="${CONFIG_UI.urlLogo}" style="width:100%; max-height:15vh; object-fit:contain; border-radius:8px;"></div>` : '';

        overlay.innerHTML = `
            ${htmlLogo}
            <div class="k-header">
                <h1 style="color:var(--acc-titolo); margin:0; font-size:2.2rem; letter-spacing:-1px;">${CONFIG.titoloDashboard}</h1>
                <div id="kiosk-orologio" style="font-size:3rem; font-weight:bold; color:var(--acc-orologio); line-height:1;">--:--</div>
            </div>
            <div id="kiosk-dashboard" style="flex-grow: 1; overflow-y: hidden;"></div>
        `;
        document.body.appendChild(overlay);
    }

    const orologio = document.getElementById('kiosk-orologio');
    if (orologio) orologio.innerText = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', hour12: !CONFIG.formatoOrario24h });

    const nodiEventi = document.querySelectorAll('.fc-event');
    const dashboard = document.getElementById('kiosk-dashboard');
    if (!dashboard) return;

    const impegniEstratti = [];
    const now = new Date();

    nodiEventi.forEach(nodo => {
        const nodoTime = nodo.querySelector('.fc-time');
        const nodoTitle = nodo.querySelector('.fc-title');
        if (!nodoTime || !nodoTitle) return;

        const orariMatch = nodoTime.innerText.trim().match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/);
        if (!orariMatch) return;

        const [hInizio, mInizio] = orariMatch[1].split(':').map(Number);
        const [hFine, mFine] = orariMatch[2].split(':').map(Number);

        const dataInizio = new Date(); dataInizio.setHours(hInizio, mInizio, 0, 0);
        const dataFine = new Date(); dataFine.setHours(hFine, mFine, 0, 0);

        if (now > dataFine) return;

        const righe = nodoTitle.innerText.trim().split(/\n|\r\n/).map(r => r.trim()).filter(r => r.length > 0);
        let titolo = righe[0] || "Evento";
        let docente = "", aula = "";

        for (let i = 1; i < righe.length; i++) {
            let riga = righe[i], rLow = riga.toLowerCase();
            if (rLow.includes('docent')) docente = riga.replace(/docent[ei]:?/i, '').trim();
            else if (rLow.includes('aul') || rLow.includes('sala') || rLow.includes('lab') || rLow.includes('allestimento')) {
                aula = riga.replace(/^(aul[ea]|sala):\s*/i, '').trim();
            }
        }

        if (aula !== "") {
            CONFIG.testiDaRimuovere.forEach(testo => { aula = aula.replace(new RegExp(testo, 'gi'), ''); });
            aula = aula.replace(/\s*\(.*?\)/g, '');
            aula = aula.trim().replace(/^-|-$/g, '').trim();
            if (!aula.toLowerCase().startsWith('aula') && !aula.toLowerCase().startsWith('sala')) aula = "Aula " + aula;
        } else { aula = "Da definire"; }

        impegniEstratti.push({ dataInizio: dataInizio, orario: `${orariMatch[1]} - ${orariMatch[2]}`, titolo: titolo, docente: docente, aula: aula, inCorso: (now >= dataInizio && now <= dataFine) });
    });

    impegniEstratti.sort((a, b) => a.dataInizio - b.dataInizio);

    let htmlInCorso = '', htmlFuturi = '';

    impegniEstratti.forEach(imp => {
        const cls = imp.inCorso ? 'in-corso' : '';
        const cardHTML = `
            <div class="k-card ${cls}">
                <div class="k-card-top">
                    <div class="k-orario">${imp.orario}</div>
                    <div class="k-aula">${imp.aula}</div>
                </div>
                <div class="k-titolo">${imp.titolo}</div>
                <div class="k-docente">${imp.docente}</div>
            </div>
        `;
        if (imp.inCorso) htmlInCorso += cardHTML;
        else htmlFuturi += cardHTML;
    });

    if (!htmlInCorso) htmlInCorso = '<div style="font-size:1.4rem; color:#484f58; font-style:italic; padding:10px 0;">Nessuna lezione in questo momento</div>';
    if (!htmlFuturi) htmlFuturi = '<div style="font-size:1.4rem; color:#484f58; font-style:italic; padding:10px 0;">Nessuna lezione programmata</div>';

    let nuovoHTML = '';
    if (impegniEstratti.length === 0) {
        nuovoHTML = '<div style="text-align:center; font-size:2rem; margin-top:50px; color:#8b949e;">Nessun impegno attivo per la giornata.</div>';
    } else {
        if (isLandscape) {
            nuovoHTML = `
                <div style="display:flex; gap:30px; height:100%; align-items:flex-start;">
                    <div style="flex:1; width:50%;"><h2 class="k-col-title">In Corso</h2>${htmlInCorso}</div>
                    <div style="flex:1; width:50%;"><h2 class="k-col-title">Prossimi Eventi</h2>${htmlFuturi}</div>
                </div>
            `;
        } else {
            nuovoHTML = `
                <div style="display:flex; flex-direction:column; gap:25px;">
                    <div><h2 class="k-col-title">In Corso</h2>${htmlInCorso}</div>
                    <div><h2 class="k-col-title">Prossimi Eventi</h2>${htmlFuturi}</div>
                </div>
            `;
        }
    }

    if (dashboard.innerHTML !== nuovoHTML) dashboard.innerHTML = nuovoHTML;
    fetch(`${CONFIG.serverLocaleUrl}/update`, { method: 'POST', body: JSON.stringify(impegniEstratti) }).catch(() => { });

}, CONFIG.cicloLetturaDati);

// HARD RESET
setTimeout(() => { window.location.reload(); }, CONFIG.intervalloHardReset);