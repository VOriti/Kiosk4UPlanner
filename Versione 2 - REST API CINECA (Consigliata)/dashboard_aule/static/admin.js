function escapeHTML(valore) {
    return String(valore ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function apriLightbox(voce) {
    const modal = document.getElementById('lightbox-modal');
    const img = document.getElementById('lightbox-img');
    const caption = document.getElementById('lightbox-caption');
    if (!modal || !img || !caption) return;
    img.src = './locandine/' + encodeURIComponent(voce.nome);
    caption.textContent = `${voce.nome} · ${voce.kb} KB · ${voce.caricata}`;
    modal.style.display = 'flex';
}

function chiudiLightbox() {
    const modal = document.getElementById('lightbox-modal');
    if (modal) modal.style.display = 'none';
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        chiudiLightbox();
    }
});

let currentConfig = {};

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-Admin-Token': sessionStorage.getItem('adminToken')
    };
}

let loginCountdownTimer = null;

async function login() {
    const pwd = document.getElementById('login-password').value;
    if (!pwd) return;

    try {
        const res = await fetch('./api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pwd })
        });

        if (res.ok) {
            if (loginCountdownTimer) { clearInterval(loginCountdownTimer); loginCountdownTimer = null; }
            const data = await res.json();
            sessionStorage.setItem('adminToken', data.token);
            document.getElementById('login-error').style.display = 'none';
            loadAdminData();
        } else {
            const errEl = document.getElementById('login-error');
            errEl.style.color = "var(--danger-color)";
            try {
                const errData = await res.json();
                let sec = errData.secondi_attesa;
                if (!sec && errData.error) {
                    const m = errData.error.match(/(\d+)\s+secondi/);
                    if (m) sec = parseInt(m[1]);
                }
                if (sec && sec > 0) {
                    if (loginCountdownTimer) clearInterval(loginCountdownTimer);
                    errEl.innerText = `🚨 Troppi tentativi falliti. Riprova tra ${sec} secondi.`;
                    errEl.style.display = 'block';
                    loginCountdownTimer = setInterval(() => {
                        sec--;
                        if (sec <= 0) {
                            clearInterval(loginCountdownTimer);
                            loginCountdownTimer = null;
                            errEl.innerText = "Puoi riprovare ad accedere ora.";
                            errEl.style.color = "var(--accent-color, #58a6ff)";
                        } else {
                            errEl.innerText = `🚨 Troppi tentativi falliti. Riprova tra ${sec} secondi.`;
                        }
                    }, 1000);
                    return;
                }
                errEl.innerText = errData.error || "Password errata.";
            } catch {
                errEl.innerText = "Password errata.";
            }
            errEl.style.display = 'block';
        }
    } catch (e) {
        console.error(e);
        alert("Errore di rete durante il login.");
    }
}

function logout() {
    sessionStorage.removeItem('adminToken');
    showView('login-view');
}

async function loadAdminData(config) {
    if (config) {
        currentConfig = config;
        populateForm(config);
        return;
    }
    const token = sessionStorage.getItem('adminToken');
    if (!token) {
        showView('login-view');
        return;
    }

    try {
        const res = await fetch('./api/admin/config_full', { headers: getAuthHeaders() });
        if (res.status === 401 || res.status === 403) {
            sessionStorage.removeItem('adminToken');
            showView('login-view');
            return;
        }

        if (res.ok) {
            currentConfig = await res.json();
            populateForm(currentConfig);
            aggiornaElencoLocandine();
            showView('admin-view');
        }
    } catch (e) {
        console.error(e);
        showView('login-view');
    }
}

function populateForm(config) {
    // Banner sicurezza
    const banner = document.getElementById('security-banner');
    banner.style.display = config.avviso_sicurezza ? 'block' : 'none';

    // Sicurezza
    document.getElementById('admin_attivo').checked = config.sicurezza?.admin_attivo || false;
    document.getElementById('debug_mode').checked = config.main?.debug_mode || false;
    document.getElementById('admin_ip_autorizzati').value = (config.sicurezza?.admin_ip_autorizzati || []).join(', ');
    document.getElementById('admin_password').value = '';
    document.getElementById('porta_server').value = config.main?.porta_server || 8080;

    // HTTPS
    const httpsCfg = config.https || {};
    document.getElementById('https_abilitato').checked = httpsCfg.abilitato === true;
    document.getElementById('https_porta').value = httpsCfg.porta_https || 8443;
    document.getElementById('https_certificato').value = httpsCfg.file_certificato || 'cert.pem';
    document.getElementById('https_chiave').value = httpsCfg.file_chiave || 'key.pem';
    document.getElementById('https_forza_redirect').checked = httpsCfg.forza_redirect_http === true;
    toggleHttpsFields();

    // Preview URL Schermi Secondari Digital Signage
    const srvPort = config.main?.porta_server || '8080';
    const srvHost = window.location.hostname || 'IP_RASPBERRY';
    const srvProto = window.location.protocol || 'http:';
    const previewEl = document.getElementById('kiosk-url-preview');
    if (previewEl) {
        const portSuffix = (srvPort == '80' && srvProto == 'http:') || (srvPort == '443' && srvProto == 'https:') ? '' : `:${srvPort}`;
        previewEl.innerText = `${srvProto}//${srvHost}${portSuffix}/?kiosk=1`;
    }

    // API CINECA
    document.getElementById('cineca_username').value = config.api_cineca?.username || '';
    document.getElementById('cineca_password').value = config.api_cineca?.password || '';
    document.getElementById('cineca_realm').value = config.api_cineca?.realm || '';
    document.getElementById('cineca_edificio').value = config.api_cineca?.id_edificio || '';
    document.getElementById('anno_accademico_id').value = config.api_cineca?.anno_accademico_id || '';
    document.getElementById('contesto_id').value = config.api_cineca?.contesto_id || '';
    document.getElementById('cineca_intervallo').value = config.api_cineca?.intervallo_aggiornamento_sec || 300;
    document.getElementById('cineca_url').value = config.api_cineca?.url_base || '';

    // Frontend
    document.getElementById('fe_mostra_confermati').checked = config.frontend?.mostra_confermati !== false;
    document.getElementById('fe_mostra_stato').checked = config.frontend?.mostraStatoPC !== false;
    document.getElementById('fe_carosello').checked = config.frontend?.caroselloAttivo !== false;
    document.getElementById('fe_titolo').value = config.frontend?.titoloSede || '';
    document.getElementById('fe_logo').value = config.frontend?.urlLogo || '';
    document.getElementById('fe_url_calendario').value = config.frontend?.urlCalendario || '';
    document.getElementById('fe_pausa_carosello').value = config.frontend?.pausaTraCaroselli || 180000;
    document.getElementById('fe_expo_locandina').value = config.frontend?.esposizioneLocandina || 10000;
    document.getElementById('fe_intervallo').value = config.frontend?.intervalloAggiornamento || 5000;
    let quotaVal = 30;
    const rawQuota = config.frontend?.quotaCarosello;
    if (typeof rawQuota === 'number' && Number.isFinite(rawQuota)) {
        if (rawQuota >= 0.10 && rawQuota <= 0.50) {
            quotaVal = Math.round(rawQuota * 100);
        } else if (rawQuota >= 10 && rawQuota <= 50) {
            quotaVal = Math.round(rawQuota);
        }
    }
    const sliderQuota = document.getElementById('fe_quota_carosello');
    if (sliderQuota) sliderQuota.value = quotaVal;
    const badgeQuota = document.getElementById('fe_quota_carosello_val');
    if (badgeQuota) badgeQuota.textContent = quotaVal + '%';

    // Footer News
    const fn = config.footer_news || {};
    document.getElementById('fn_abilitato').checked = fn.abilitato !== false;
    document.getElementById('fn_stile').value = fn.stile_scorrimento || 'orizzontale';
    document.getElementById('fn_velocita').value = fn.velocita || 50;
    document.getElementById('fn_colore_testo').value = fn.colore_testo || '#c9d1d9';
    document.getElementById('fn_colore_sfondo').value = fn.colore_sfondo || '#161b22';
    document.getElementById('fn_colore_btn').value = fn.colore_btn || '#30363d';
    document.getElementById('fn_dimensione_testo').value = fn.dimensione_testo || '1.15rem';
    document.getElementById('fn_alert_attivo').checked = fn.alert_fisso_attivo || false;
    document.getElementById('fn_alert_testo').value = fn.alert_testo || '';

    const fonti = fn.fonti || [];
    const diagNews = config.diagnostica_news || {};
    const container = document.getElementById('fonti_container');
    container.innerHTML = '';
    for (let i = 0; i < 6; i++) {
        const f = fonti[i] || { abilitata: false, nome: '', url: '', tipo: 'rss', visibile_di_default: true, peso: 1 };
        const html = `
            <div class="fonte-card">
                <div class="fonte-card-header">
                    <h4 class="fonte-card-title">Fonte ${i + 1}</h4>
                    <span id="fn_f${i}_diagnostica" class="status-badge fonte-diag-badge"></span>
                </div>
                <div class="fonte-checkboxes">
                    <div class="form-group form-group-checkbox fonte-checkbox-group">
                        <input type="checkbox" id="fn_f${i}_abilitata" ${f.abilitata !== false ? 'checked' : ''}>
                        <label for="fn_f${i}_abilitata">Abilitata (Scarica news)</label>
                    </div>
                    <div class="form-group form-group-checkbox fonte-checkbox-group">
                        <input type="checkbox" id="fn_f${i}_visibile" ${f.visibile_di_default !== false ? 'checked' : ''}>
                        <label for="fn_f${i}_visibile">Visibile di default sul Kiosk</label>
                    </div>
                </div>
                <div class="fonte-row">
                    <div class="form-group fonte-col-1">
                        <label>Nome Fonte</label>
                        <input type="text" id="fn_f${i}_nome" value="${escapeHTML(f.nome || '')}">
                    </div>
                    <div class="form-group fonte-col-2">
                        <label>URL</label>
                        <input type="text" id="fn_f${i}_url" value="${escapeHTML(f.url || '')}">
                    </div>
                </div>
                <div class="fonte-row-meta">
                    <div class="form-group fonte-col-1">
                        <label>Formato Dati</label>
                        <select id="fn_f${i}_tipo" class="admin-select-full">
                            <option value="rss" ${f.tipo === 'rss' ? 'selected' : ''}>Feed RSS (XML)</option>
                            <option value="rest" ${f.tipo === 'rest' ? 'selected' : ''}>REST API (JSON)</option>
                        </select>
                    </div>
                    <div class="form-group fonte-col-1">
                        <label title="Intero da 1 (default) a 5. Le fonti vengono mescolate a turno e a ogni giro una fonte inserisce fino a 'Peso' notizie di fila: con Peso 2 contro 1 una fonte compare il doppio più spesso. Valori fuori range vengono riportati a 1-5.">Peso (1-5) ℹ️</label>
                        <input type="number" id="fn_f${i}_peso" min="1" max="5" value="${f.peso || 1}" class="admin-input-full">
                    </div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);

        const badgeDiag = document.getElementById(`fn_f${i}_diagnostica`);
        if (badgeDiag) {
            const u = (f.url || '').trim();
            badgeDiag.title = u;
            if (!u) {
                badgeDiag.textContent = '⚪ Non configurata';
                badgeDiag.style.color = '#8b949e';
                badgeDiag.style.backgroundColor = 'rgba(110, 118, 129, 0.1)';
                badgeDiag.style.border = '1px solid #30363d';
            } else if (f.abilitata === false) {
                badgeDiag.textContent = '⚪ Disattivata';
                badgeDiag.style.color = '#8b949e';
                badgeDiag.style.backgroundColor = 'rgba(110, 118, 129, 0.1)';
                badgeDiag.style.border = '1px solid #30363d';
            } else if (!diagNews || !diagNews[u]) {
                badgeDiag.textContent = '⚪ In attesa del primo aggiornamento';
                badgeDiag.style.color = '#8b949e';
                badgeDiag.style.backgroundColor = 'rgba(110, 118, 129, 0.1)';
                badgeDiag.style.border = '1px solid #30363d';
            } else {
                const d = diagNews[u];
                if (d.stato === 'OK') {
                    badgeDiag.textContent = `🟢 OK: ${d.articoli} notizie (ore ${d.ora})`;
                    badgeDiag.style.color = '#3fb950';
                    badgeDiag.style.backgroundColor = 'rgba(63, 185, 80, 0.15)';
                    badgeDiag.style.border = '1px solid rgba(63, 185, 80, 0.4)';
                } else if (d.stato === 'DISABILITATA') {
                    badgeDiag.textContent = '⚪ Disattivata';
                    badgeDiag.style.color = '#8b949e';
                    badgeDiag.style.backgroundColor = 'rgba(110, 118, 129, 0.1)';
                    badgeDiag.style.border = '1px solid #30363d';
                } else {
                    badgeDiag.textContent = `🔴 Errore: ${d.stato} (ore ${d.ora})`;
                    badgeDiag.style.color = '#f85149';
                    badgeDiag.style.backgroundColor = 'rgba(248, 81, 73, 0.15)';
                    badgeDiag.style.border = '1px solid rgba(248, 81, 73, 0.4)';
                }
            }
        }
    }

    aggiornaBadgesSommario();
}

function switchTab(tabId) {
    document.querySelectorAll('.admin-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const btn = document.getElementById(`tab-btn-${tabId}`);
    const content = document.getElementById(`tab-content-${tabId}`);
    if (btn) btn.classList.add('active');
    if (content) content.classList.add('active');
}

function toggleAccordion(id) {
    const panel = document.getElementById(id);
    if (panel) {
        panel.classList.toggle('open');
        if (id === 'panel-locandine' && panel.classList.contains('open')) {
            aggiornaElencoLocandine();
        }
    }
}

function setAllAccordions(open) {
    const activeTab = document.querySelector('.tab-content.active') || document;
    activeTab.querySelectorAll('.accordion-panel').forEach(p => {
        if (open) p.classList.add('open');
        else p.classList.remove('open');
    });
}

function aggiornaBadgesSommario() {
    // 1. Alert Giallo
    const alertAttivo = document.getElementById('fn_alert_attivo')?.checked;
    const alertTesto = document.getElementById('fn_alert_testo')?.value.trim();
    const badgeAlert = document.getElementById('badge-summary-alert');
    const previewContainer = document.getElementById('alert-preview-container');
    const previewText = document.getElementById('alert-preview-text');
    if (badgeAlert) {
        if (alertAttivo) {
            badgeAlert.className = 'status-badge badge-warn';
            badgeAlert.innerText = 'ATTIVO';
            if (previewContainer) previewContainer.style.display = 'block';
            if (previewText) previewText.innerText = alertTesto || '(Nessun testo inserito)';
        } else {
            badgeAlert.className = 'status-badge badge-off';
            badgeAlert.innerText = 'NON ATTIVO';
            if (previewContainer) previewContainer.style.display = 'none';
        }
    }

    // 2. Rete e Sicurezza
    const porta = document.getElementById('porta_server')?.value || '8080';
    const adminAttivo = document.getElementById('admin_attivo')?.checked;
    const badgeRete = document.getElementById('badge-summary-rete');
    if (badgeRete) {
        badgeRete.className = 'status-badge badge-info';
        badgeRete.innerText = `Porta ${porta} ${adminAttivo ? '• Admin ON' : '• Admin OFF'}`;
    }

    // 3. HTTPS
    const httpsAttivo = document.getElementById('https_abilitato')?.checked;
    const httpsPorta = document.getElementById('https_porta')?.value || '8443';
    const badgeHttps = document.getElementById('badge-summary-https');
    if (badgeHttps) {
        if (httpsAttivo) {
            badgeHttps.className = 'status-badge badge-on';
            badgeHttps.innerText = `ATTIVO: ${httpsPorta}`;
        } else {
            badgeHttps.className = 'status-badge badge-off';
            badgeHttps.innerText = 'DISABILITATO';
        }
    }

    // 4. CINECA + Salvaguardia Anno Accademico e Contesto (v5.3.6)
    const edificio = document.getElementById('cineca_edificio')?.value.trim();
    const userCineca = document.getElementById('cineca_username')?.value.trim();
    const pwdCineca = document.getElementById('cineca_password')?.value || '';
    const debugAttivo = document.getElementById('debug_mode')?.checked === true;
    const annoEl = document.getElementById('anno_accademico_id');
    const contestoEl = document.getElementById('contesto_id');
    const lblAnno = document.querySelector('label[for="anno_accademico_id"]');
    const lblContesto = document.querySelector('label[for="contesto_id"]');
    const paginazioneSupportata = currentConfig.paginazione_cineca_supportata === true;
    const filtriObbligatori = Boolean(userCineca && pwdCineca && !paginazioneSupportata && !debugAttivo);
    const safeIdPattern = /^[a-zA-Z0-9_-]{4,64}$/;
    const annoVal = (annoEl?.value || '').trim().replace(/^[\s"']+|[\s"']+$/g, '');
    const contestoVal = (contestoEl?.value || '').trim().replace(/^[\s"']+|[\s"']+$/g, '');
    const annoInvalido = (filtriObbligatori && !annoVal) || (Boolean(annoVal) && !safeIdPattern.test(annoVal));
    const contestoInvalido = (filtriObbligatori && !contestoVal) || (Boolean(contestoVal) && !safeIdPattern.test(contestoVal));

    if (lblAnno) {
        lblAnno.textContent = (userCineca && pwdCineca && !paginazioneSupportata)
            ? (debugAttivo ? 'ID Anno Accademico (Scoperta via Debug Mode attiva)' : 'ID Anno Accademico (Obbligatorio)')
            : 'ID Anno Accademico';
    }
    if (lblContesto) {
        lblContesto.textContent = (userCineca && pwdCineca && !paginazioneSupportata)
            ? (debugAttivo ? 'ID Contesto — Polo / Dipartimento / Area (Scoperta via Debug Mode attiva)' : 'ID Contesto — Polo / Dipartimento / Area (Obbligatorio)')
            : 'ID Contesto — Polo / Dipartimento / Area';
    }
    if (annoEl) {
        annoEl.style.borderColor = annoInvalido ? 'var(--danger-color)' : '';
    }
    if (contestoEl) {
        contestoEl.style.borderColor = contestoInvalido ? 'var(--danger-color)' : '';
    }

    const badgeCineca = document.getElementById('badge-summary-cineca');
    if (badgeCineca) {
        if (annoInvalido || contestoInvalido) {
            badgeCineca.className = 'status-badge badge-warn';
            badgeCineca.innerText = 'ID Anno/Contesto da verificare';
        } else if (debugAttivo && userCineca && (!annoVal || !contestoVal)) {
            badgeCineca.className = 'status-badge badge-warn';
            badgeCineca.innerText = 'Debug: scoperta ID in kiosk.log';
        } else if (edificio) {
            badgeCineca.className = 'status-badge badge-info';
            badgeCineca.innerText = `Edificio: ${edificio}`;
        } else if (userCineca) {
            badgeCineca.className = 'status-badge badge-info';
            badgeCineca.innerText = 'Intero Contesto';
        } else {
            badgeCineca.className = 'status-badge badge-off';
            badgeCineca.innerText = 'Non configurato';
        }
    }

    // 5. Locandine
    const carosello = document.getElementById('fe_carosello')?.checked;
    const badgeLocandine = document.getElementById('badge-summary-locandine') || document.getElementById('badge-summary-frontend');
    if (badgeLocandine) {
        if (carosello) {
            badgeLocandine.className = 'status-badge badge-on';
            badgeLocandine.innerText = 'Locandine: ON';
        } else {
            badgeLocandine.className = 'status-badge badge-off';
            badgeLocandine.innerText = 'Locandine: OFF';
        }
    }

    // 6. Footer News
    const fnAttivo = document.getElementById('fn_abilitato')?.checked;
    let numFontiAttive = 0;
    for (let i = 0; i < 6; i++) {
        const chk = document.getElementById(`fn_f${i}_abilitata`);
        const nome = document.getElementById(`fn_f${i}_nome`);
        if (chk && chk.checked && nome && nome.value.trim()) numFontiAttive++;
    }
    const badgeFooter = document.getElementById('badge-summary-footer');
    if (badgeFooter) {
        if (fnAttivo) {
            badgeFooter.className = 'status-badge badge-on';
            badgeFooter.innerText = `Attivo (${numFontiAttive} ${numFontiAttive === 1 ? 'fonte' : 'fonti'})`;
        } else {
            badgeFooter.className = 'status-badge badge-off';
            badgeFooter.innerText = 'DISABILITATO';
        }
    }
}

function toggleHttpsFields() {
    const isChecked = document.getElementById('https_abilitato').checked;
    const container = document.getElementById('https-fields-container');
    if (container) {
        container.style.display = isChecked ? 'block' : 'none';
    }
}

async function salvaConfigurazione(riavvia) {
    const sanitizeId = (val) => (val || '').replace(/^[\s"']+|[\s"']+$/g, '');
    const ips = document.getElementById('admin_ip_autorizzati').value.split(',').map(s => s.trim()).filter(s => s);
    const annoId = sanitizeId(document.getElementById('anno_accademico_id').value);
    const contestoId = sanitizeId(document.getElementById('contesto_id').value);
    const realm = sanitizeId(document.getElementById('cineca_realm').value);
    const edificio = sanitizeId(document.getElementById('cineca_edificio').value);
    const intervallo = parseInt(document.getElementById('cineca_intervallo').value) || 300;
    const safeIdPattern = /^[a-zA-Z0-9_-]{4,64}$/;
    const hexPattern = /^[0-9a-fA-F]{24}$/;

    const evidenziaPannelloCineca = () => {
        switchTab('sistema');
        const panelCineca = document.getElementById('panel-cineca');
        if (panelCineca && !panelCineca.classList.contains('open')) {
            panelCineca.classList.add('open');
        }
        aggiornaBadgesSommario();
        panelCineca?.scrollIntoView({ behavior: 'smooth' });
    };

    if (annoId && !safeIdPattern.test(annoId)) {
        evidenziaPannelloCineca();
        alert("ID Anno Accademico non valido: inserire un codice identificativo pulito (4-64 caratteri alfanumerici, senza spazi o simboli; su U-Planner sono 24 caratteri esadecimali).");
        return;
    }

    if (contestoId && !safeIdPattern.test(contestoId)) {
        evidenziaPannelloCineca();
        alert("ID Contesto non valido: inserire un codice identificativo pulito (4-64 caratteri alfanumerici, senza spazi o simboli; su U-Planner sono 24 caratteri esadecimali).");
        return;
    }

    if (annoId && !hexPattern.test(annoId)) {
        if (!confirm(`Attenzione: l'ID Anno Accademico inserito ("${annoId}", ${annoId.length} caratteri) non ha il formato standard U-Planner di 24 caratteri esadecimali (0-9, a-f).\n\nSe si tratta di un errore di copia-incolla o di un testo di prova premi "Annulla".\nPremi "OK" solo se il tuo Ateneo utilizza codici personalizzati.`)) {
            evidenziaPannelloCineca();
            return;
        }
    }

    if (contestoId && !hexPattern.test(contestoId)) {
        if (!confirm(`Attenzione: l'ID Contesto inserito ("${contestoId}", ${contestoId.length} caratteri) non ha il formato standard U-Planner di 24 caratteri esadecimali (0-9, a-f).\n\nSe si tratta di un errore di copia-incolla o di un testo di prova premi "Annulla".\nPremi "OK" solo se il tuo Ateneo utilizza codici personalizzati.`)) {
            evidenziaPannelloCineca();
            return;
        }
    }

    const payload = {
        main: {
            ...currentConfig.main,
            porta_server: document.getElementById('porta_server').value,
            debug_mode: document.getElementById('debug_mode').checked
        },
        https: {
            ...currentConfig.https,
            abilitato: document.getElementById('https_abilitato').checked,
            porta_https: parseInt(document.getElementById('https_porta').value) || 8443,
            file_certificato: document.getElementById('https_certificato').value.trim() || 'cert.pem',
            file_chiave: document.getElementById('https_chiave').value.trim() || 'key.pem',
            forza_redirect_http: document.getElementById('https_forza_redirect').checked
        },
        sicurezza: {
            admin_attivo: document.getElementById('admin_attivo').checked,
            admin_ip_autorizzati: ips
        },
        api_cineca: {
            username: document.getElementById('cineca_username').value.trim(),
            password: document.getElementById('cineca_password').value,
            realm: realm,
            id_edificio: edificio,
            anno_accademico_id: annoId,
            contesto_id: contestoId,
            intervallo_aggiornamento_sec: intervallo,
            url_base: document.getElementById('cineca_url').value.trim()
        },
        frontend: {
            ...currentConfig.frontend,
            mostra_confermati: document.getElementById('fe_mostra_confermati').checked,
            mostraStatoPC: document.getElementById('fe_mostra_stato').checked,
            caroselloAttivo: document.getElementById('fe_carosello').checked,
            titoloSede: document.getElementById('fe_titolo').value,
            urlLogo: document.getElementById('fe_logo').value,
            urlCalendario: document.getElementById('fe_url_calendario').value,
            pausaTraCaroselli: parseInt(document.getElementById('fe_pausa_carosello').value),
            esposizioneLocandina: parseInt(document.getElementById('fe_expo_locandina').value),
            intervalloAggiornamento: parseInt(document.getElementById('fe_intervallo').value),
            quotaCarosello: parseFloat((parseInt(document.getElementById('fe_quota_carosello').value) / 100).toFixed(2))
        },
        footer_news: {
            ...currentConfig.footer_news,
            abilitato: document.getElementById('fn_abilitato').checked,
            stile_scorrimento: document.getElementById('fn_stile').value,
            velocita: parseInt(document.getElementById('fn_velocita').value) || 50,
            colore_testo: document.getElementById('fn_colore_testo').value,
            colore_sfondo: document.getElementById('fn_colore_sfondo').value,
            colore_btn: document.getElementById('fn_colore_btn').value,
            dimensione_testo: document.getElementById('fn_dimensione_testo').value,
            alert_fisso_attivo: document.getElementById('fn_alert_attivo').checked,
            alert_testo: document.getElementById('fn_alert_testo').value,
            fonti: Array.from({ length: 6 }).map((_, i) => ({
                abilitata: document.getElementById(`fn_f${i}_abilitata`).checked,
                nome: document.getElementById(`fn_f${i}_nome`).value.trim(),
                url: document.getElementById(`fn_f${i}_url`).value.trim(),
                tipo: document.getElementById(`fn_f${i}_tipo`).value,
                visibile_di_default: document.getElementById(`fn_f${i}_visibile`).checked,
                peso: parseInt(document.getElementById(`fn_f${i}_peso`).value) || 1
            }))
        }
    };

    const nuovaPwd = document.getElementById('admin_password').value;
    if (nuovaPwd) {
        payload.admin_password = nuovaPwd;
    }

    try {
        const res = await fetch('./api/admin/save', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            showToast();
            document.getElementById('admin_password').value = '';

            if (riavvia) {
                await fetch('./api/admin/restart', { method: 'POST', headers: getAuthHeaders() });
                startRestartCountdown();
            } else {
                loadAdminData();
            }
        } else {
            const errData = await res.json().catch(() => ({}));
            const msgErr = errData.error || "Errore durante il salvataggio";
            if (msgErr.includes('anno_accademico_id') || msgErr.includes('contesto_id')) {
                switchTab('sistema');
                const panelCineca = document.getElementById('panel-cineca');
                if (panelCineca && !panelCineca.classList.contains('open')) {
                    panelCineca.classList.add('open');
                }
                aggiornaBadgesSommario();
                panelCineca?.scrollIntoView({ behavior: 'smooth' });
            }
            alert(msgErr);
        }
    } catch (e) {
        console.error(e);
        alert("Errore di rete");
    }
}

const saveAdminData = salvaConfigurazione;

function showView(viewId) {
    document.getElementById('login-view').classList.remove('active');
    document.getElementById('admin-view').classList.remove('active');
    document.getElementById(viewId).classList.add('active');
}

let toastTimeout = null;
function showToast(messaggio) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    if (toastTimeout) {
        clearTimeout(toastTimeout);
        toastTimeout = null;
    }
    toast.textContent = messaggio || "Salvato con successo!";
    toast.classList.remove("show");
    void toast.offsetWidth;
    toast.classList.add("show");
    toastTimeout = setTimeout(() => {
        toast.classList.remove("show");
        toast.textContent = "Salvato con successo!";
        toastTimeout = null;
    }, 3000);
}

function startRestartCountdown() {
    const modal = document.getElementById('restart-modal');
    const cd = document.getElementById('countdown');
    modal.style.display = 'flex';
    let seconds = 5;
    const timer = setInterval(() => {
        seconds--;
        cd.innerText = seconds;
        if (seconds <= 0) {
            clearInterval(timer);
            window.location.reload();
        }
    }, 1000);
}

let locandineOperazioneInCorso = false;

const LATO_MAX_LOCANDINA = 2160;

function calcolaDimensioniLocandina(larghezza, altezza, latoMax) {
    const scala = Math.min(1, latoMax / Math.max(larghezza, altezza));
    return { larghezza: Math.round(larghezza * scala), altezza: Math.round(altezza * scala), ridimensiona: scala < 1 };
}

async function preparaLocandina(file) {
    const bitmap = await createImageBitmap(file);
    const dim = calcolaDimensioniLocandina(bitmap.width, bitmap.height, LATO_MAX_LOCANDINA);
    if (!dim.ridimensiona && file.size <= 2 * 1024 * 1024) { bitmap.close(); return file; }
    const canvas = document.createElement('canvas');
    canvas.width = dim.larghezza; canvas.height = dim.altezza;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0, dim.larghezza, dim.altezza);
    bitmap.close();
    let blob = await new Promise(r => canvas.toBlob(r, 'image/webp', 0.85));
    if (!blob || blob.type !== 'image/webp') {            // browser senza encoder WebP: JPEG su fondo bianco
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, dim.larghezza, dim.altezza);
        blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.85));
    }
    return blob;
}

async function caricaLocandine() {
    if (locandineOperazioneInCorso) return;
    const input = document.getElementById('locandine_file');
    if (!input || !input.files || input.files.length === 0) {
        alert('Seleziona almeno un file immagine da caricare.');
        return;
    }

    const MAX_SIZE = 10 * 1024 * 1024;
    const files = Array.from(input.files);

    locandineOperazioneInCorso = true;
    try {
        const token = sessionStorage.getItem('adminToken');
        let qualcheRidimensionata = false;
        for (const file of files) {
            let blob;
            try {
                blob = await preparaLocandina(file);
            } catch (err) {
                console.error(`Errore elaborazione immagine "${file.name}":`, err);
                await aggiornaElencoLocandine();
                alert(`Impossibile elaborare l'immagine "${file.name}". Assicurati che sia un'immagine valida (JPEG, PNG o WebP).`);
                return;
            }
            if (blob !== file) {
                qualcheRidimensionata = true;
            }
            if (blob.size > MAX_SIZE) {
                await aggiornaElencoLocandine();
                alert(`Il file "${file.name}" supera il limite massimo consentito di 10 MB.`);
                return;
            }
            try {
                const res = await fetch('./api/admin/locandine/upload', {
                    method: 'POST',
                    headers: {
                        'X-Admin-Token': token,
                        'Content-Type': blob.type || 'application/octet-stream'
                    },
                    body: blob
                });
                if (!res.ok) {
                    let errText = `Errore HTTP ${res.status}`;
                    try {
                        const errJson = await res.json();
                        if (errJson && errJson.error) errText = errJson.error;
                    } catch (_) {}
                    await aggiornaElencoLocandine();
                    alert(`Errore durante il caricamento di "${file.name}": ${errText}`);
                    return;
                }
            } catch (err) {
                console.error(err);
                await aggiornaElencoLocandine();
                alert(`Errore di rete durante il caricamento di "${file.name}".`);
                return;
            }
        }

        input.value = '';
        await aggiornaElencoLocandine();
        showToast(qualcheRidimensionata ? "Locandina ridimensionata e caricata con successo!" : "Locandina caricata con successo!");
    } finally {
        locandineOperazioneInCorso = false;
    }
}

let elencoLocandineCache = [];

async function spostaLocandina(index, offset) {
    if (locandineOperazioneInCorso) return;
    const nuovoIndex = index + offset;
    if (nuovoIndex < 0 || nuovoIndex >= elencoLocandineCache.length) return;
    locandineOperazioneInCorso = true;
    const nomi = elencoLocandineCache.map(item => item.nome);
    const temp = nomi[index];
    nomi[index] = nomi[nuovoIndex];
    nomi[nuovoIndex] = temp;

    try {
        const res = await fetch('./api/admin/locandine/ordine', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ ordine: nomi })
        });
        if (res.ok) {
            await aggiornaElencoLocandine();
            showToast();
        } else {
            let errText = `Errore HTTP ${res.status}`;
            try {
                const errJson = await res.json();
                if (errJson && errJson.error) errText = errJson.error;
            } catch (_) {}
            alert(`Errore durante il riordino: ${errText}`);
        }
    } catch (e) {
        console.error('Errore riordino locandine:', e);
        alert('Errore di rete durante il riordino delle locandine.');
    } finally {
        locandineOperazioneInCorso = false;
    }
}

async function eliminaLocandina(nome) {
    if (locandineOperazioneInCorso) return;
    if (!confirm(`Sei sicuro di voler eliminare la locandina "${nome}"?`)) {
        return;
    }
    locandineOperazioneInCorso = true;
    try {
        const res = await fetch('./api/admin/locandine/elimina', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ filename: nome })
        });
        if (res.ok) {
            await aggiornaElencoLocandine();
            showToast();
        } else {
            let errText = `Errore HTTP ${res.status}`;
            try {
                const errJson = await res.json();
                if (errJson && errJson.error) errText = errJson.error;
            } catch (_) {}
            alert(`Errore durante l'eliminazione: ${errText}`);
        }
    } catch (e) {
        console.error('Errore eliminazione locandina:', e);
        alert('Errore di rete durante l\'eliminazione della locandina.');
    } finally {
        locandineOperazioneInCorso = false;
    }
}

async function aggiornaElencoLocandine() {
    try {
        const res = await fetch('./api/admin/locandine', { headers: getAuthHeaders() });
        if (res.status === 401 || res.status === 403) return;
        if (!res.ok) return;
        const lista = await res.json();
        elencoLocandineCache = Array.isArray(lista) ? lista : [];
        const ul = document.getElementById('locandine_lista');
        if (!ul) return;
        ul.textContent = '';
        if (elencoLocandineCache.length === 0) {
            const li = document.createElement('li');
            li.className = 'locandina-empty';
            li.textContent = 'Nessuna locandina presente.';
            ul.appendChild(li);
            return;
        }
        elencoLocandineCache.forEach((v, index) => {
            const li = document.createElement('li');
            li.className = 'locandina-item';

            const colSinistra = document.createElement('div');
            colSinistra.className = 'locandina-left';

            const colThumb = document.createElement('div');
            colThumb.className = 'locandina-thumb-col';
            colThumb.innerHTML = `<img class="miniatura-locandina" loading="lazy" alt="" src="./locandine/${escapeHTML(encodeURIComponent(v.nome))}">`;
            const imgEl = colThumb.querySelector('img');
            if (imgEl) imgEl.addEventListener('click', () => apriLightbox(v));

            const colInfo = document.createElement('div');
            colInfo.className = 'locandina-info-col';

            const nomeSpan = document.createElement('span');
            nomeSpan.className = 'locandina-nome';
            nomeSpan.textContent = v.nome;

            const metaSpan = document.createElement('span');
            metaSpan.className = 'locandina-meta';
            metaSpan.textContent = `${v.kb} KB • Caricata: ${v.caricata}`;

            colInfo.appendChild(nomeSpan);
            colInfo.appendChild(metaSpan);

            colSinistra.appendChild(colThumb);
            colSinistra.appendChild(colInfo);

            const colAzioni = document.createElement('div');
            colAzioni.className = 'locandina-actions';

            const btnSu = document.createElement('button');
            btnSu.type = 'button';
            btnSu.textContent = '▲';
            btnSu.title = 'Sposta in alto';
            btnSu.setAttribute('aria-label', `Sposta in alto ${v.nome}`);
            btnSu.className = 'btn btn-loc-move';
            if (index === 0) {
                btnSu.disabled = true;
            } else {
                btnSu.addEventListener('click', () => spostaLocandina(index, -1));
            }

            const btnGiu = document.createElement('button');
            btnGiu.type = 'button';
            btnGiu.textContent = '▼';
            btnGiu.title = 'Sposta in basso';
            btnGiu.setAttribute('aria-label', `Sposta in basso ${v.nome}`);
            btnGiu.className = 'btn btn-loc-move';
            if (index === elencoLocandineCache.length - 1) {
                btnGiu.disabled = true;
            } else {
                btnGiu.addEventListener('click', () => spostaLocandina(index, 1));
            }

            const btnElimina = document.createElement('button');
            btnElimina.type = 'button';
            btnElimina.textContent = '🗑';
            btnElimina.title = 'Elimina locandina';
            btnElimina.setAttribute('aria-label', `Elimina locandina ${v.nome}`);
            btnElimina.className = 'btn btn-loc-delete';
            btnElimina.addEventListener('click', () => eliminaLocandina(v.nome));

            colAzioni.appendChild(btnSu);
            colAzioni.appendChild(btnGiu);
            colAzioni.appendChild(btnElimina);

            li.appendChild(colSinistra);
            li.appendChild(colAzioni);
            ul.appendChild(li);
        });
    } catch (e) {
        console.error('Errore durante la lettura di locandine:', e);
    }
}

function collegaEventiAdmin() {
    const loginPwd = document.getElementById('login-password');
    if (loginPwd) {
        loginPwd.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') login();
        });
    }

    const btnLogin = document.getElementById('btn-login');
    if (btnLogin) btnLogin.addEventListener('click', login);

    const securityBanner = document.getElementById('security-banner');
    if (securityBanner) {
        securityBanner.addEventListener('click', () => {
            switchTab('sistema');
            toggleAccordion('panel-rete');
            document.getElementById('panel-rete')?.scrollIntoView({ behavior: 'smooth' });
        });
    }

    const btnExpandAll = document.getElementById('btn-expand-all');
    if (btnExpandAll) btnExpandAll.addEventListener('click', () => setAllAccordions(true));

    const btnCollapseAll = document.getElementById('btn-collapse-all');
    if (btnCollapseAll) btnCollapseAll.addEventListener('click', () => setAllAccordions(false));

    const tabPers = document.getElementById('tab-btn-personalizzazione');
    if (tabPers) tabPers.addEventListener('click', () => switchTab('personalizzazione'));

    const tabSist = document.getElementById('tab-btn-sistema');
    if (tabSist) tabSist.addEventListener('click', () => switchTab('sistema'));

    document.querySelectorAll('.accordion-header[data-accordion-target]').forEach((header) => {
        header.addEventListener('click', () => {
            toggleAccordion(header.dataset.accordionTarget);
        });
    });

    const quotaSlider = document.getElementById('fe_quota_carosello');
    if (quotaSlider) {
        const aggiornaQuotaLabel = () => {
            const valEl = document.getElementById('fe_quota_carosello_val');
            if (valEl) valEl.textContent = quotaSlider.value + '%';
        };
        quotaSlider.addEventListener('input', aggiornaQuotaLabel);
        quotaSlider.addEventListener('change', aggiornaQuotaLabel);
    }

    const btnCarica = document.getElementById('btn-carica-locandine');
    if (btnCarica) btnCarica.addEventListener('click', caricaLocandine);

    const httpsChk = document.getElementById('https_abilitato');
    if (httpsChk) {
        httpsChk.addEventListener('change', () => {
            toggleHttpsFields();
            aggiornaBadgesSommario();
        });
    }

    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) btnLogout.addEventListener('click', logout);

    const btnSalva = document.getElementById('btn-salva');
    if (btnSalva) btnSalva.addEventListener('click', () => salvaConfigurazione(false));

    const btnSalvaRiavvia = document.getElementById('btn-salva-riavvia');
    if (btnSalvaRiavvia) btnSalvaRiavvia.addEventListener('click', () => salvaConfigurazione(true));

    const lightboxModal = document.getElementById('lightbox-modal');
    if (lightboxModal) {
        lightboxModal.addEventListener('click', (event) => {
            if (event.target === lightboxModal || event.target.id === 'lightbox-close-btn') {
                chiudiLightbox();
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    collegaEventiAdmin();

    const adminView = document.getElementById('admin-view');
    if (adminView) {
        adminView.addEventListener('input', aggiornaBadgesSommario);
        adminView.addEventListener('change', aggiornaBadgesSommario);
    }

    if (sessionStorage.getItem('adminToken')) {
        loadAdminData();
    } else {
        showView('login-view');
    }
});
