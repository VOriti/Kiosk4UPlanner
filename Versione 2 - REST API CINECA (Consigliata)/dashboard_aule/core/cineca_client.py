"""Client REST autonomo per CINECA U-Planner (backoff esponenziale N-05, timeout 15s, motore D-01)."""
import datetime
import logging
import random
import re
import threading
import time
from typing import Optional

import requests

LIMITE_EVENTI_CINECA = 500          # tetto 'limit' richiesto a getImpegniCalendario
MAX_PAGINE_CINECA = 10              # tetto massimo pagine in caso di paginazione supportata
SOGLIA_ASSENZE_ANNULLAMENTO = 2     # polling consecutivi senza l'evento prima di marcarlo ANNULLATO
AVVISI_DI_STATO = ("ANNULLATO", "SOSPESO")
BACKOFF_BASE_SEC = 120.0
BACKOFF_MAX_SEC = 3600.0
RE_ID_CINECA_SICURO = re.compile(r'^[a-zA-Z0-9_\-]{4,64}$')


def sanitize_id_str(val) -> str:
    """Sanitizza gli identificativi CINECA rimuovendo spazi e apici accidentali ed evitando 'None'."""
    if val is None:
        return ''
    return re.sub(r"^[\s\'\"]+|[\s\'\"]+$", '', str(val))


def get_tz_roma():
    """Restituisce il fuso orario di Roma (Europe/Rome).

    Supporta nativamente zoneinfo su Linux/Raspberry Pi con fallback robusto per Windows/UTC.
    """
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo("Europe/Rome")
    except Exception:
        pass
    local_now = datetime.datetime.now().astimezone()
    local_tz = local_now.tzinfo
    if local_tz and local_now.utcoffset() != datetime.timedelta(0):
        return local_tz
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    anno = now_utc.year
    mar_last_sun = max(d for d in range(25, 32) if datetime.date(anno, 3, d).weekday() == 6)
    oct_last_sun = max(d for d in range(25, 32) if datetime.date(anno, 10, d).weekday() == 6)
    dst_start = datetime.datetime(anno, 3, mar_last_sun, 2, 0, tzinfo=datetime.timezone.utc)
    dst_end = datetime.datetime(anno, 10, oct_last_sun, 3, 0, tzinfo=datetime.timezone.utc)
    offset_ore = 2 if dst_start <= now_utc < dst_end else 1
    return datetime.timezone(datetime.timedelta(hours=offset_ore))


def get_giorno_operativo(dt_roma=None) -> datetime.date:
    """Calcola la data del giorno operativo corrente per l'Ateneo (04:00 - 03:59)."""
    tz_roma = get_tz_roma()
    now_roma = dt_roma or datetime.datetime.now(tz_roma)
    if now_roma.hour >= 4:
        return now_roma.date()
    return now_roma.date() - datetime.timedelta(days=1)


def _estrai_titolo_e_avviso(item, stato):
    """Estrae titolo formattato e stato di annullamento/sospensione da un record CINECA."""
    is_cancellato = (stato == 'A')
    avviso_stato = ""
    if stato == 'A':
        avviso_stato = "ANNULLATO"
    elif stato == 'S':
        avviso_stato = "SOSPESO"

    evento = item.get('evento') or {}
    is_indisponibilita = (
        item.get('indisponibilita', False)
        or item.get('indisponibilitaTotale', False)
        or item.get('indisponibilitaTotaleAule', False)
        or item.get('tipoImpegno') == 'INDISPONIBILITA'
    )
    dettaglio = evento.get('dettaglioDidattico') if isinstance(evento, dict) else {}
    testo_estratto = (
        item.get('nome')
        or item.get('causaleIndisponibilita')
        or item.get('note')
        or (evento.get('nome') if isinstance(evento, dict) else None)
        or item.get('motivo')
        or item.get('descrizione')
        or (dettaglio.get('nome') if isinstance(dettaglio, dict) else None)
        or "Attività programmata"
    )
    titolo_raw = f"INDISPONIBILITÀ: {testo_estratto}" if is_indisponibilita else testo_estratto
    return titolo_raw.strip(), is_cancellato, avviso_stato


class CinecaClient:
    """Client HTTP autonomo per l'API REST CINECA U-Planner con backoff esponenziale e motore D-01."""

    def __init__(self, url_base, realm, username, password, timeout=15, usa_jitter=True):
        self.url_base = str(url_base or 'https://cineca.prod.up.cineca.it/api').strip().rstrip('/')
        self.realm = sanitize_id_str(realm)
        self.username = str(username or '')
        self.password = str(password or '')
        self.timeout = float(timeout)
        self.usa_jitter = bool(usa_jitter)
        self.token = None
        self.fallimenti_consecutivi = 0
        self.prossimo_tentativo_login = 0.0
        self.ultimo_backoff_applicato = 0.0
        self.paginazione_supportata = False
        self.parametro_paginazione = None
        self._lock = threading.Lock()

    def calcola_backoff(self, tentativi=None) -> float:
        """Calcola il ritardo esponenziale N-05 (120s -> 3600s max, con jitter opzionale)."""
        n = max(1, int(self.fallimenti_consecutivi if tentativi is None else tentativi))
        ritardo = min(BACKOFF_MAX_SEC, BACKOFF_BASE_SEC * (2 ** (n - 1)))
        if self.usa_jitter:
            jitter = random.uniform(0.0, min(30.0, 0.1 * ritardo))
            ritardo = min(BACKOFF_MAX_SEC, ritardo + jitter)
        return float(ritardo)

    def puo_tentare_login(self, now=None) -> bool:
        """Indica se la finestra di backoff corrente è scaduta."""
        now_ts = time.time() if now is None else float(now)
        with self._lock:
            return now_ts >= self.prossimo_tentativo_login

    def secondi_al_prossimo_tentativo(self, now=None) -> float:
        """Restituisce i secondi mancanti allo scadere del backoff attivo."""
        now_ts = time.time() if now is None else float(now)
        with self._lock:
            return max(0.0, self.prossimo_tentativo_login - now_ts)

    def reset_backoff(self):
        """Azzera i contatori di backoff dopo autenticazione o sync riuscito."""
        with self._lock:
            self.fallimenti_consecutivi = 0
            self.prossimo_tentativo_login = 0.0
            self.ultimo_backoff_applicato = 0.0

    def invalida_token(self):
        """Invalida il token corrente forzando un nuovo login al ciclo successivo."""
        with self._lock:
            self.token = None

    def login(self, now=None) -> Optional[str]:
        """Esegue login verso CINECA rispettando il backoff esponenziale e timeout 15s."""
        now_ts = time.time() if now is None else float(now)
        with self._lock:
            if now_ts < self.prossimo_tentativo_login:
                restanti = max(1, int(self.prossimo_tentativo_login - now_ts))
                logging.warning(f"⏳ Login CINECA in backoff attivo: riprova tra {restanti}s.")
                return None
            url_login = f"{self.url_base}/Utenti/login"
            payload = {
                "username": self.username,
                "password": self.password,
                "realm": self.realm,
                "clientId": self.realm,
            }
            timeout = self.timeout

        logging.info("Richiesta di un nuovo Token a CINECA (Admin) in corso...")
        motivo = ""
        try:
            risposta = requests.post(url_login, json=payload, timeout=timeout)
            if risposta.status_code == 200:
                dati = risposta.json() if hasattr(risposta, 'json') else {}
                tok = (dati.get("id") or dati.get("token")) if isinstance(dati, dict) else None
                if tok:
                    with self._lock:
                        self.token = tok
                        self.fallimenti_consecutivi = 0
                        self.prossimo_tentativo_login = 0.0
                        self.ultimo_backoff_applicato = 0.0
                    logging.info("✅ Login CINECA riuscito. Nuovo token acquisito.")
                    return tok
                motivo = "Risposta 200 priva di token"
            else:
                motivo = f"HTTP {risposta.status_code} ({getattr(risposta, 'text', '')[:100]})"
        except Exception as e:
            motivo = f"Errore di rete: {e}"

        with self._lock:
            self.token = None
            self.fallimenti_consecutivi += 1
            n_tentativo = self.fallimenti_consecutivi
            ritardo = self.calcola_backoff(n_tentativo)
            self.ultimo_backoff_applicato = ritardo
            self.prossimo_tentativo_login = now_ts + ritardo

        logging.error(
            f"❌ Errore Login CINECA (tentativo #{n_tentativo}): {motivo}. "
            f"Backoff attivato per {int(ritardo)}s."
        )
        return None

    def fetch_impegni(
        self,
        giorno_op,
        anno_accademico_id='',
        contesto_id='',
        limit=LIMITE_EVENTI_CINECA,
        extra_params=None,
    ) -> Optional[list]:
        """Recupera gli impegni del giorno operativo da getImpegniCalendario con timeout esplicito."""
        if not self.token and not self.login():
            return None

        tz_roma = get_tz_roma()
        dt_inizio_roma = datetime.datetime.combine(giorno_op, datetime.time(0, 0, 0), tzinfo=tz_roma)
        dt_fine_roma = datetime.datetime.combine(giorno_op, datetime.time(23, 59, 59), tzinfo=tz_roma)
        inizio_giornata = dt_inizio_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fine_giornata = dt_fine_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        payload = {
            "limit": int(limit),
            "dataInizio": inizio_giornata,
            "dataFine": fine_giornata,
            "mostraImpegniSenzaAula": False,
            "nascondiIndisponibilitaParziali": False,
        }
        anno_id = sanitize_id_str(anno_accademico_id)
        if anno_id:
            payload["annoAccademicoId"] = anno_id
        ctx_id = sanitize_id_str(contesto_id)
        if ctx_id:
            payload["contestoId"] = ctx_id
        if isinstance(extra_params, dict):
            payload.update(extra_params)

        with self._lock:
            token_corrente = self.token
            realm_corrente = self.realm
            url_impegni = f"{self.url_base}/Impegni/getImpegniCalendario"
            timeout = self.timeout

        headers = {
            "Authorization": token_corrente,
            "Content-Type": "application/json",
            "X-Realm": realm_corrente,
        }
        try:
            risposta = requests.post(url_impegni, json=payload, headers=headers, timeout=timeout)
        except Exception as e:
            logging.error(f"❌ Errore di rete durante fetch impegni CINECA: {e}")
            return None

        if risposta.status_code == 401:
            logging.error("❌ Token scaduto o non valido (401). Forzo il rinnovo.")
            self.invalida_token()
            return None

        if risposta.status_code == 200:
            self.reset_backoff()
            dati_grezzi = risposta.json()
            if (
                extra_params is None
                and self.paginazione_supportata
                and self.parametro_paginazione
                and isinstance(dati_grezzi, list)
                and len(dati_grezzi) >= int(limit)
            ):
                raccolti = list(dati_grezzi)
                visti = {
                    str(x.get('id') or x.get('_id'))
                    for x in raccolti
                    if isinstance(x, dict) and (x.get('id') or x.get('_id'))
                }
                for pagina_idx in range(1, MAX_PAGINE_CINECA):
                    param = self.parametro_paginazione
                    val_pag = (pagina_idx + 1) if param == 'page' else pagina_idx * int(limit)
                    payload_pag = dict(payload)
                    payload_pag[param] = val_pag
                    try:
                        risp_pag = requests.post(url_impegni, json=payload_pag, headers=headers, timeout=timeout)
                    except Exception as e:
                        logging.warning(f"⚠️ Interruzione recupero paginato alla pagina {pagina_idx + 1}: {e}")
                        break
                    if risp_pag.status_code != 200:
                        break
                    pagina_dati = risp_pag.json()
                    if not isinstance(pagina_dati, list) or not pagina_dati:
                        break
                    nuovi = 0
                    for elem in pagina_dati:
                        chiave = str(elem.get('id') or elem.get('_id')) if isinstance(elem, dict) else ''
                        if chiave and chiave in visti:
                            continue
                        if chiave:
                            visti.add(chiave)
                        raccolti.append(elem)
                        nuovi += 1
                    if nuovi == 0 or len(pagina_dati) < int(limit):
                        break
                return raccolti
            self.verifica_sentinella_limite(dati_grezzi)
            return dati_grezzi

        logging.error(f"❌ Errore HTTP {risposta.status_code}: {getattr(risposta, 'text', '')[:100]}")
        return None

    def verifica_supporto_paginazione(
        self,
        giorno_op,
        anno_accademico_id='',
        contesto_id='',
    ) -> dict:
        """Sonda diagnostica su getImpegniCalendario per verificare se skip/offset/page sono supportati (ST-05 / D-17)."""
        if not self.token and not self.login():
            self.paginazione_supportata = False
            self.parametro_paginazione = None
            return {
                "supportata": False,
                "parametro": None,
                "motivo": "Autenticazione CINECA non disponibile",
            }

        tz_roma = get_tz_roma()
        dt_inizio_roma = datetime.datetime.combine(giorno_op, datetime.time(0, 0, 0), tzinfo=tz_roma)
        dt_fine_roma = datetime.datetime.combine(giorno_op, datetime.time(23, 59, 59), tzinfo=tz_roma)
        inizio_giornata = dt_inizio_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fine_giornata = dt_fine_roma.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        base_payload = {
            "limit": 5,
            "dataInizio": inizio_giornata,
            "dataFine": fine_giornata,
            "mostraImpegniSenzaAula": False,
            "nascondiIndisponibilitaParziali": False,
        }
        anno_id = sanitize_id_str(anno_accademico_id)
        if anno_id:
            base_payload["annoAccademicoId"] = anno_id
        ctx_id = sanitize_id_str(contesto_id)
        if ctx_id:
            base_payload["contestoId"] = ctx_id

        with self._lock:
            token_corrente = self.token
            realm_corrente = self.realm
            url_impegni = f"{self.url_base}/Impegni/getImpegniCalendario"
            timeout = self.timeout

        headers = {
            "Authorization": token_corrente,
            "Content-Type": "application/json",
            "X-Realm": realm_corrente,
        }

        def _estrai_ids(elementi):
            if not isinstance(elementi, list):
                return set()
            return {
                str(el.get('id') or el.get('_id'))
                for el in elementi
                if isinstance(el, dict) and (el.get('id') or el.get('_id'))
            }

        try:
            risp_p1 = requests.post(
                url_impegni,
                json={**base_payload, "skip": 0},
                headers=headers,
                timeout=timeout,
            )
        except Exception as e:
            self.paginazione_supportata = False
            self.parametro_paginazione = None
            return {
                "supportata": False,
                "parametro": None,
                "motivo": f"Errore di rete durante sonda paginazione: {e}",
            }

        if risp_p1.status_code != 200:
            self.paginazione_supportata = False
            self.parametro_paginazione = None
            return {
                "supportata": False,
                "parametro": None,
                "motivo": "Parametri skip/offset/page ignorati o rifiutati da CINECA UP",
            }

        ids_p1 = _estrai_ids(risp_p1.json())
        if not ids_p1:
            self.paginazione_supportata = False
            self.parametro_paginazione = None
            return {
                "supportata": False,
                "parametro": None,
                "motivo": "Impegni insufficienti per verificare la paginazione; attiva modalita' conservativa",
            }

        for nome_param, valore_p2 in (("skip", 5), ("offset", 5), ("page", 2)):
            try:
                risp_p2 = requests.post(
                    url_impegni,
                    json={**base_payload, nome_param: valore_p2},
                    headers=headers,
                    timeout=timeout,
                )
            except Exception:
                continue
            if risp_p2.status_code != 200:
                continue
            ids_p2 = _estrai_ids(risp_p2.json())
            if ids_p2 and ids_p1.isdisjoint(ids_p2):
                self.paginazione_supportata = True
                self.parametro_paginazione = nome_param
                logging.info(f"✅ Sonda paginazione CINECA: parametro '{nome_param}' supportato.")
                return {
                    "supportata": True,
                    "parametro": nome_param,
                    "motivo": "Paginazione verificata",
                }

        self.paginazione_supportata = False
        self.parametro_paginazione = None
        logging.info(
            "ℹ️ Sonda paginazione CINECA: parametri skip/offset/page ignorati o rifiutati da CINECA UP. "
            "Attiva salvaguardia obbligatoria su anno_accademico_id e contesto_id."
        )
        return {
            "supportata": False,
            "parametro": None,
            "motivo": "Parametri skip/offset/page ignorati o rifiutati da CINECA UP",
        }

    @staticmethod
    def valida_configurazione_salvaguardia(config_dict) -> bool:
        """Verifica che anno_accademico_id e contesto_id siano entrambi valorizzati e con formato ID sicuro (4-64 char)."""
        if not isinstance(config_dict, dict):
            return False
        api = config_dict.get('api_cineca')
        if not isinstance(api, dict):
            return False
        anno = sanitize_id_str(api.get('anno_accademico_id'))
        contesto = sanitize_id_str(api.get('contesto_id'))
        return bool(
            anno
            and contesto
            and RE_ID_CINECA_SICURO.match(anno)
            and RE_ID_CINECA_SICURO.match(contesto)
        )

    def scopri_anagrafiche_debug(self, anno_accademico_id='', contesto_id='') -> dict:
        """Interroga /AnniAccademici e /Contesti in Debug Mode e registra le mappe leggibili in kiosk.log."""
        if not self.token and not self.login():
            return {"anni_accademici": [], "contesti": []}

        anno_corrente_cfg = sanitize_id_str(anno_accademico_id)
        contesto_corrente_cfg = sanitize_id_str(contesto_id)

        with self._lock:
            token_corrente = self.token
            realm_corrente = self.realm
            url_base = self.url_base
            timeout = self.timeout

        headers = {
            "Authorization": token_corrente,
            "Content-Type": "application/json",
            "X-Realm": realm_corrente,
        }

        adesso_utc = datetime.datetime.now(datetime.timezone.utc)
        voci_anni = []
        try:
            risp_anni = requests.get(f"{url_base}/AnniAccademici", headers=headers, timeout=timeout)
            if risp_anni.status_code == 200:
                dati_anni = risp_anni.json()
                if isinstance(dati_anni, list):
                    anni_ordinati = sorted(
                        (a for a in dati_anni if isinstance(a, dict)),
                        key=lambda x: str(x.get('codice') or x.get('descrizione') or ''),
                    )
                    for a in anni_ordinati:
                        aid = sanitize_id_str(a.get('id') or a.get('_id'))
                        if not aid:
                            continue
                        cod = str(a.get('codice') or '').strip()
                        desc = str(a.get('descrizione') or a.get('nome') or cod or 'N/D').strip()
                        tag = []
                        try:
                            ini_str = str(a.get('dataInizio') or '').replace('Z', '+00:00')
                            fin_str = str(a.get('dataFine') or '').replace('Z', '+00:00')
                            if ini_str and fin_str:
                                dt_i = datetime.datetime.fromisoformat(ini_str)
                                dt_f = datetime.datetime.fromisoformat(fin_str)
                                if dt_i <= adesso_utc <= dt_f:
                                    tag.append("ANNO IN CORSO")
                        except Exception:
                            pass
                        if aid == anno_corrente_cfg:
                            tag.append("IN USO")
                        suffisso = f" [{' | '.join(tag)}]" if tag else ""
                        etichetta = f"{desc} (cod. '{cod}')" if cod and cod != desc else desc
                        voci_anni.append(f"{etichetta} -> ID '{aid}'{suffisso}")
                if voci_anni:
                    logging.info(f"🕵️ DEBUG MAPPA ANNI ACCADEMICI RILEVATI ({len(voci_anni)}): {voci_anni}")
                else:
                    logging.info("🕵️ DEBUG MAPPA ANNI ACCADEMICI: Nessun anno accademico restituito da CINECA.")
            else:
                logging.warning(f"🕵️ DEBUG MAPPA ANNI ACCADEMICI: HTTP {risp_anni.status_code} su /AnniAccademici.")
        except Exception as e:
            logging.warning(f"🕵️ DEBUG MAPPA ANNI ACCADEMICI non disponibile: {e}")

        voci_contesti = []
        try:
            risp_ctx = requests.get(f"{url_base}/Contesti", headers=headers, timeout=timeout)
            if risp_ctx.status_code == 200:
                dati_ctx = risp_ctx.json()
                if isinstance(dati_ctx, list):
                    ctx_ordinati = sorted(
                        (c for c in dati_ctx if isinstance(c, dict)),
                        key=lambda x: (
                            str(x.get('codice') or '').lower(),
                            str(x.get('descrizione') or x.get('nome') or '').lower(),
                        ),
                    )
                    for c in ctx_ordinati:
                        cid = sanitize_id_str(c.get('id') or c.get('_id'))
                        if not cid:
                            continue
                        cod = str(c.get('codice') or '').strip()
                        desc = str(c.get('descrizione') or c.get('nome') or 'Nessuna descrizione').strip()
                        suffisso = " [IN USO]" if cid == contesto_corrente_cfg else ""
                        voci_contesti.append(f"Codice '{cod}' ({desc}) -> ID '{cid}'{suffisso}")
                if voci_contesti:
                    logging.info(f"🕵️ DEBUG MAPPA CONTESTI RILEVATI ({len(voci_contesti)}): {voci_contesti}")
                else:
                    logging.info("🕵️ DEBUG MAPPA CONTESTI: Nessun contesto restituito da CINECA.")
            else:
                logging.warning(f"🕵️ DEBUG MAPPA CONTESTI: HTTP {risp_ctx.status_code} su /Contesti.")
        except Exception as e:
            logging.warning(f"🕵️ DEBUG MAPPA CONTESTI non disponibile: {e}")

        return {"anni_accademici": voci_anni, "contesti": voci_contesti}

    @staticmethod
    def verifica_sentinella_limite(dati_grezzi) -> bool:
        """Segnala nel log una risposta CINECA arrivata al tetto 'limit' (possibile troncatura)."""
        if isinstance(dati_grezzi, list) and len(dati_grezzi) >= LIMITE_EVENTI_CINECA:
            logging.warning(
                f"⚠️ SENTINELLA LIMITE CINECA: ricevuti {len(dati_grezzi)} impegni "
                f"(limite {LIMITE_EVENTI_CINECA}). Possibile troncatura: valorizzare anno_accademico_id e contesto_id."
            )
            return True
        return False

    @staticmethod
    def processa_impegni(
        impegni_grezzi,
        storico_impegni,
        id_edificio='',
        mostra_confermati=True,
        ora_attuale=None,
    ) -> tuple[list, bool]:
        """Elabora gli impegni CINECA applicando filtri non distruttivi e motore D-01 su storico_impegni."""
        tz_roma = get_tz_roma()
        if ora_attuale is None:
            ora_attuale = datetime.datetime.now(tz_roma)
        elif ora_attuale.tzinfo is None:
            ora_attuale = ora_attuale.replace(tzinfo=tz_roma)

        id_edificio_norm = sanitize_id_str(id_edificio)
        nuovi_estratti = {}
        id_esclusi = set()
        id_illeggibili = set()

        for item in impegni_grezzi:
            id_imp = (item.get('id') or item.get('_id')) if isinstance(item, dict) else None
            if not id_imp:
                continue
            try:
                aule = item.get('aule', [])
                edifici_impegno = [
                    sanitize_id_str(a.get('edificio', {}).get('codice'))
                    for a in aule
                    if isinstance(a, dict) and a.get('edificio')
                ]

                if id_edificio_norm != "":
                    edifici_norm = set(edifici_impegno) | {c.lstrip('0') or '0' for c in edifici_impegno}
                    id_norm = id_edificio_norm.lstrip('0') or '0'
                    if id_edificio_norm not in edifici_norm and id_norm not in edifici_norm:
                        id_esclusi.add(id_imp)
                        continue

                stato = item.get('stato', 'P')
                if isinstance(stato, dict):
                    stato = stato.get('codice') or stato.get('id') or 'P'
                stato = str(stato).upper().strip()

                if stato == 'B':
                    id_esclusi.add(id_imp)
                    continue

                if stato == 'C' and not mostra_confermati:
                    id_esclusi.add(id_imp)
                    continue

                titolo_raw, is_cancellato, avviso_stato = _estrai_titolo_e_avviso(item, stato)
                str_inizio = item.get('dataInizio', '').replace('Z', '+00:00')
                str_fine = item.get('dataFine', '').replace('Z', '+00:00')
                dt_inizio = datetime.datetime.fromisoformat(str_inizio)
                dt_fine = datetime.datetime.fromisoformat(str_fine)

                docenti = item.get('docenti')
                docente_str = (
                    f"{docenti[0].get('cognome', '')} {docenti[0].get('nome', '')}".strip()
                    if docenti
                    else "Dipartimento"
                )
                aula_str = (aule[0].get('descrizione') or 'Da definire').strip() if aule else "Da definire"

                nuovi_estratti[id_imp] = {
                    "id": id_imp,
                    "orario": f"{dt_inizio.astimezone(tz_roma).strftime('%H:%M')} - {dt_fine.astimezone(tz_roma).strftime('%H:%M')}",
                    "titolo": titolo_raw,
                    "docente": docente_str,
                    "aula": aula_str,
                    "inCorso": (dt_inizio <= ora_attuale <= dt_fine),
                    "timestamp_inizio": dt_inizio.timestamp(),
                    "timestamp_fine": dt_fine.timestamp(),
                    "cancellato": is_cancellato,
                    "avviso": avviso_stato,
                    "stato_cineca": stato,
                    "assenze": 0,
                }
            except Exception as e:
                id_illeggibili.add(id_imp)
                logging.warning(f"⚠️ Impegno CINECA {id_imp} non interpretabile ({e}): stato precedente preservato.")

        # Un evento escluso dai filtri NON è annullato: esce semplicemente dallo storico
        for id_escluso in id_esclusi:
            storico_impegni.pop(id_escluso, None)

        for id_nuovo, imp_nuovo in nuovi_estratti.items():
            if id_nuovo not in storico_impegni:
                storico_impegni[id_nuovo] = imp_nuovo
            else:
                imp_storico = storico_impegni[id_nuovo]

                # Auto-healing: l'evento è di nuovo regolare in CINECA, si rimuove l'avviso di stato ereditato
                if not imp_nuovo['avviso'] and imp_storico.get('avviso') in AVVISI_DI_STATO:
                    imp_storico['avviso'] = ""
                    imp_storico['cancellato'] = False

                cambiata_aula = imp_storico['aula'] != imp_nuovo['aula']
                cambiato_orario = imp_storico['orario'] != imp_nuovo['orario']

                if (cambiata_aula or cambiato_orario) and not imp_storico.get('avviso', '').startswith("Spostato"):
                    vecchia_aula = imp_storico['aula']
                    vecchio_orario = imp_storico['orario']
                    imp_storico['avviso'] = f"Spostato (da {vecchia_aula} ore {vecchio_orario})"

                if imp_nuovo['avviso']:
                    imp_storico['avviso'] = imp_nuovo['avviso']
                    imp_storico['cancellato'] = imp_nuovo['cancellato']
                else:
                    imp_nuovo['avviso'] = imp_storico.get('avviso', "")

                imp_storico.update(imp_nuovo)

        # Protezione anti-falso annullamento su risposta CINECA vuota
        if len(impegni_grezzi) == 0 and len(storico_impegni) > 0:
            logging.warning(
                "⚠️ Rilevato payload CINECA vuoto a fronte di impegni validi in memoria. "
                "Preservo lo stato per evitare falsi annullamenti."
            )
            preservato = True
        else:
            preservato = False
            for id_storico, imp_storico in storico_impegni.items():
                if id_storico in nuovi_estratti or id_storico in id_illeggibili:
                    continue
                if imp_storico['timestamp_fine'] > ora_attuale.timestamp() and not imp_storico.get('cancellato'):
                    imp_storico['assenze'] = imp_storico.get('assenze', 0) + 1
                    if imp_storico['assenze'] >= SOGLIA_ASSENZE_ANNULLAMENTO:
                        imp_storico["cancellato"] = True
                        imp_storico["avviso"] = "ANNULLATO"
                        logging.info(
                            f"🚫 Impegno {id_storico} assente da CINECA per {imp_storico['assenze']} "
                            "polling consecutivi: marcato ANNULLATO."
                        )

        dt_inizio_giorno = datetime.datetime.combine(
            get_giorno_operativo(ora_attuale),
            datetime.time(0, 0, 0),
            tzinfo=tz_roma,
        )
        mezzanotte_oggi = dt_inizio_giorno.timestamp()
        chiavi_scadute = [k for k, v in storico_impegni.items() if v.get('timestamp_fine', 0) <= mezzanotte_oggi]
        for k in chiavi_scadute:
            del storico_impegni[k]

        now_ts = ora_attuale.timestamp()
        for imp in storico_impegni.values():
            imp['inCorso'] = (imp['timestamp_inizio'] <= now_ts <= imp['timestamp_fine'])

        dati_puliti = [imp for imp in storico_impegni.values() if imp['timestamp_fine'] > now_ts or imp['inCorso']]
        dati_puliti.sort(key=lambda x: x['timestamp_inizio'])
        return dati_puliti, preservato
