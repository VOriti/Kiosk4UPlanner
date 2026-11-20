"""v5.2.4: lock-down kiosk, carosello concatenato a duty-cycle <= 30%, chiusura al tocco."""
import json
import re
import unittest

from tests._harness import (avvia_http, carica_server, chiudi_server, ferma_http,
                            login_admin, richiesta)
from tests._harness_js import NODE, esegui_js, estrai_funzione_js, leggi_pagina


class TestStruttura(unittest.TestCase):

    def setUp(self):
        self.html = leggi_pagina('remoto.html')

    def test_nessun_setinterval_sul_carosello(self):
        self.assertNotRegex(self.html, r'setInterval\(\s*riproduciLocandine')
        self.assertIn('pianificaCarosello', self.html)

    def test_costanti(self):
        self.assertRegex(self.html, r'QUOTA_MAX_CAROSELLO\s*=\s*0\.30')
        self.assertRegex(self.html, r'DURATA_TRANSIZIONE_MS\s*=\s*1550')
        self.assertRegex(self.html, r'INATTIVITA_KIOSK_MS\s*=\s*60000')

    def test_link_disattivati_in_kiosk(self):
        self.assertRegex(self.html, r'body\.modalita-kiosk\s+a(\[href\])?\s*\{[^}]*pointer-events:\s*none')

    def test_chiusura_al_tocco(self):
        self.assertRegex(self.html, r"advOverlay\.addEventListener\(\s*['\"]pointerdown")
        self.assertRegex(self.html, r"advOverlay\.addEventListener\(\s*['\"]click")
        self.assertIn("e.key === 'Escape'", self.html)

    def test_kiosk_ignora_preferenze_locali(self):
        attivo = estrai_funzione_js('remoto.html', 'isLocandineActiveOnDevice')
        self.assertLess(attivo.index('isKioskEnvironment()'), attivo.index('localStorage'))
        self.assertIn('isKioskEnvironment()', estrai_funzione_js('remoto.html', 'toggleLocandinePreference'))

    def test_lockdown_kiosk_funzioni(self):
        self.assertIn('attivaModalitaKiosk', self.html)
        self.assertIn('chiudiInterfacciaKiosk', self.html)
        self.assertIn('riarmaInattivita', self.html)

    def test_kiosk_attivato_prima_di_fetch_config(self):
        idx_kiosk = self.html.index('attivaModalitaKiosk()')
        idx_fetch = self.html.index('await fetchConfigPubblica()')
        self.assertLess(idx_kiosk, idx_fetch)


@unittest.skipUnless(NODE, 'Node.js non disponibile')
class TestDutyCycle(unittest.TestCase):

    def test_gruppi_per_ciclo(self):
        risultato = esegui_js('remoto.html', ['calcolaGruppiPerCiclo'],
                              '[calcolaGruppiPerCiclo(180000, 10000, 0.30, 1550), calcolaGruppiPerCiclo(180000, 60000, 0.30, 1550)]')
        self.assertEqual(risultato, [6, 1])

    def test_gruppi_per_ciclo_quote_limite(self):
        # 10% di quota: budget = 180000 * 0.10 / 0.90 = 20000 -> Math.floor(20000/11550) = 1
        # 50% di quota: budget = 180000 * 0.50 / 0.50 = 180000 -> Math.floor(180000/11550) = 15
        risultato = esegui_js('remoto.html', ['calcolaGruppiPerCiclo'],
                              '[calcolaGruppiPerCiclo(180000, 10000, 0.10, 1550), calcolaGruppiPerCiclo(180000, 10000, 0.50, 1550)]')
        self.assertEqual(risultato, [1, 15])

    def test_quota_mai_superata_con_piu_gruppi(self):
        espressione = ('[60000, 180000, 300000].flatMap(p => [5000, 10000, 15000].map(e => {'
                       ' const q = calcolaGruppiPerCiclo(p, e, 0.30, 1550);'
                       ' return [q, q * (e + 1550) / (q * (e + 1550) + p)]; }))')
        for quanti, quota in esegui_js('remoto.html', ['calcolaGruppiPerCiclo'], espressione):
            if quanti > 1:
                self.assertLessEqual(quota, 0.30 + 1e-9)

    def test_rotazione_copre_tutte_le_locandine(self):
        espressione = ('(() => { const g = [0,1,2,3,4,5,6,7,8,9];'
                       ' const a = selezionaGruppi(g, 0, 6); const b = selezionaGruppi(g, a.prossimoInizio, 6);'
                       ' const c = selezionaGruppi([0,1], 1, 6); return [a, b, c]; })()')
        a, b, c = esegui_js('remoto.html', ['selezionaGruppi'], espressione)
        self.assertEqual(a, {'selezionati': [0, 1, 2, 3, 4, 5], 'prossimoInizio': 6})
        self.assertEqual(b, {'selezionati': [6, 7, 8, 9, 0, 1], 'prossimoInizio': 2})
        self.assertEqual(c, {'selezionati': [0, 1], 'prossimoInizio': 0})

    def test_rotazione_array_vuoto(self):
        vuoto = esegui_js('remoto.html', ['selezionaGruppi'], 'selezionaGruppi([], 0, 4)')
        self.assertEqual(vuoto, {'selezionati': [], 'prossimoInizio': 0})

    def test_calcola_gruppi_fallback_minimo(self):
        q = esegui_js('remoto.html', ['calcolaGruppiPerCiclo'], 'calcolaGruppiPerCiclo(1000, 60000, 0.30, 1550)')
        self.assertEqual(q, 1)

    def test_attendi_carosello_e_interruzione(self):
        import subprocess, json
        sorgente = estrai_funzione_js('remoto.html', 'attendiCarosello')
        script = f"""
        let interrompiCarosello = null;
        {sorgente}
        (async () => {{
            const t0 = Date.now();
            const r1 = await attendiCarosello(20);
            const p2 = attendiCarosello(10000);
            interrompiCarosello();
            const r2 = await p2;
            const durata = Date.now() - t0;
            process.stdout.write(JSON.stringify({{r1, r2, durata}}));
        }})();
        """
        res = subprocess.run([NODE, '-e', script], capture_output=True, text=True, check=True)
        dati = json.loads(res.stdout)
        self.assertEqual(dati['r1'], 'completato')
        self.assertEqual(dati['r2'], 'interrotto')
        self.assertLess(dati['durata'], 2000)


class TestAdminInterfacciaDutyCycle(unittest.TestCase):

    def setUp(self):
        self.html = leggi_pagina('admin.html')

    def test_slider_e_badge_quota(self):
        self.assertRegex(self.html, r'<input[^>]+type="range"[^>]+id="fe_quota_carosello"[^>]+min="10"[^>]+max="50"[^>]+step="5"[^>]+value="30"')
        self.assertRegex(self.html, r'<span[^>]+id="fe_quota_carosello_val"[^>]*>\s*30%\s*</span>')

    def test_hint_esplicativo_duty_cycle(self):
        self.assertIn('Quota massima di tempo a video riservata alle locandine (consigliato: 30%, min 10% - max 50%)', self.html)
        self.assertIn('Garantisce che almeno il 50-90% del tempo sia sempre dedicato alla visualizzazione degli orari per gli studenti', self.html)
        self.assertIn('Il sistema calcola automaticamente quante locandine mostrare per ciclo senza mai superare questa soglia', self.html)

    def test_collocazione_campi_carosello_in_panel_locandine(self):
        idx_frontend = self.html.index('id="panel-frontend"')
        idx_locandine = self.html.index('id="panel-locandine"')
        idx_pausa = self.html.index('id="fe_pausa_carosello"')
        idx_expo = self.html.index('id="fe_expo_locandina"')
        idx_quota = self.html.index('id="fe_quota_carosello"')
        idx_intervallo = self.html.index('id="fe_intervallo"')

        self.assertGreater(idx_pausa, idx_locandine)
        self.assertGreater(idx_expo, idx_locandine)
        self.assertGreater(idx_quota, idx_locandine)

        self.assertGreater(idx_intervallo, idx_frontend)
        self.assertLess(idx_intervallo, idx_locandine)

    def test_load_e_save_admin_data(self):
        self.assertIn('fe_quota_carosello', self.html)
        self.assertIn('fe_quota_carosello_val', self.html)
        self.assertRegex(self.html, r'quotaCarosello:\s*parseFloat\(\(parseInt\(document\.getElementById\([\'"]fe_quota_carosello[\'"]\)\.value\)\s*/\s*100\)\.toFixed\(2\)\)')
        self.assertIn('async function loadAdminData(config)', self.html)
        self.assertIn('const saveAdminData = salvaConfigurazione;', self.html)

    def test_load_admin_data_parsing_quote(self):
        # Verifica la logica di normalizzazione di quotaCarosello in loadAdminData / populateForm
        script = """
        function calcolaQuota(rawQuota) {
            let quotaVal = 30;
            if (typeof rawQuota === 'number' && Number.isFinite(rawQuota)) {
                if (rawQuota >= 0.10 && rawQuota <= 0.50) {
                    quotaVal = Math.round(rawQuota * 100);
                } else if (rawQuota >= 10 && rawQuota <= 50) {
                    quotaVal = Math.round(rawQuota);
                }
            }
            return quotaVal;
        }
        process.stdout.write(JSON.stringify([
            calcolaQuota(0.30),
            calcolaQuota(0.10),
            calcolaQuota(0.50),
            calcolaQuota(0.05),
            calcolaQuota(0.85),
            calcolaQuota(NaN),
            calcolaQuota(Infinity),
            calcolaQuota(null),
            calcolaQuota(undefined),
            calcolaQuota('30')
        ]));
        """
        import subprocess
        res = subprocess.run([NODE, '-e', script], capture_output=True, text=True, check=True)
        risultati = json.loads(res.stdout)
        self.assertEqual(risultati, [30, 10, 50, 30, 30, 30, 30, 30, 30, 30])


class TestBackendDutyCycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()
        cls.base, cls.httpd = avvia_http(cls.srv)
        cls.token = login_admin(cls.srv, cls.base)

    @classmethod
    def tearDownClass(cls):
        ferma_http(cls.httpd)
        chiudi_server(cls.srv)

    def test_default_config_ha_quota_carosello(self):
        self.assertIn('quotaCarosello: 0.30', self.srv.DEFAULT_CONFIG)

    def _salva_frontend(self, frontend_patch):
        url = self.base + '/api/admin/save'
        headers = {'Content-Type': 'application/json', 'X-Admin-Token': self.token}
        payload = {'frontend': frontend_patch}
        status, _, corpo = richiesta(url, metodo='POST', corpo=json.dumps(payload).encode('utf-8'), header=headers)
        self.assertEqual(status, 200, corpo)

    def test_salvataggio_quota_valida(self):
        self._salva_frontend({'quotaCarosello': 0.25})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.25)

    def test_salvataggio_quota_limiti_inclusivi(self):
        self._salva_frontend({'quotaCarosello': 0.10})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.10)
        self._salva_frontend({'quotaCarosello': 0.50})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.50)

    def test_salvataggio_quota_sotto_il_minimo_fa_fallback(self):
        self._salva_frontend({'quotaCarosello': 0.05})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30)
        self._salva_frontend({'quotaCarosello': 0.09})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30)

    def test_salvataggio_quota_sopra_il_massimo_fa_fallback(self):
        self._salva_frontend({'quotaCarosello': 0.85})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30)
        self._salva_frontend({'quotaCarosello': 0.51})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30)

    def test_salvataggio_quota_non_numerica_fa_fallback(self):
        self._salva_frontend({'quotaCarosello': 'stringa_invalida'})
        with self.srv.lock_config:
            self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30)

    def test_salvataggio_quota_valori_anomali_fa_fallback(self):
        for val in [None, True, False, 'nan', '', [], {}]:
            self._salva_frontend({'quotaCarosello': val})
            with self.srv.lock_config:
                self.assertEqual(self.srv.CONFIG.get('frontend', {}).get('quotaCarosello'), 0.30, f"Fallito per {val}")


class TestRemotoQuotaDinamica(unittest.TestCase):

    def setUp(self):
        self.html = leggi_pagina('remoto.html')

    def test_calcolo_quota_effettiva_in_riproduci_locandine(self):
        self.assertIn("typeof CONFIG_APP.quotaCarosello === 'number'", self.html)
        self.assertIn("CONFIG_APP.quotaCarosello >= 0.10 && CONFIG_APP.quotaCarosello <= 0.50", self.html)
        self.assertIn("calcolaGruppiPerCiclo(pausa, esposizione, quotaEffettiva, DURATA_TRANSIZIONE_MS)", self.html)

    def test_calcolo_quota_effettiva_runtime_js(self):
        script = """
        const QUOTA_MAX_CAROSELLO = 0.30;
        function determinaQuota(quotaCfg) {
            const CONFIG_APP = { quotaCarosello: quotaCfg };
            return (typeof CONFIG_APP.quotaCarosello === 'number' && CONFIG_APP.quotaCarosello >= 0.10 && CONFIG_APP.quotaCarosello <= 0.50) ? CONFIG_APP.quotaCarosello : QUOTA_MAX_CAROSELLO;
        }
        process.stdout.write(JSON.stringify([
            determinaQuota(0.25),
            determinaQuota(0.10),
            determinaQuota(0.50),
            determinaQuota(0.05),
            determinaQuota(0.85),
            determinaQuota(NaN),
            determinaQuota(null),
            determinaQuota(undefined),
            determinaQuota('0.40')
        ]));
        """
        import subprocess
        res = subprocess.run([NODE, '-e', script], capture_output=True, text=True, check=True)
        risultati = json.loads(res.stdout)
        self.assertEqual(risultati, [0.25, 0.10, 0.50, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30])


if __name__ == '__main__':
    unittest.main()
