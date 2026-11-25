"""Contesto di runtime per singolo edificio: stato in RAM, lock I/O scorporati (ST-09), reset atomico (ST-11.1) e locandine."""
import contextlib
import copy
import datetime
import json
import logging
import os
import re
import secrets
import threading
import time

from core.cineca_client import get_giorno_operativo, get_tz_roma

ESTENSIONI_LOCANDINE = ('.png', '.jpg', '.jpeg', '.webp')
RE_DATA_RESET = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def rileva_formato_immagine(testa: bytes):
    """Estensione dedotta dai magic bytes, None se il formato non è ammesso."""
    if testa.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if testa.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if testa[:4] == b'RIFF' and testa[8:12] == b'WEBP':
        return '.webp'
    return None


def chiave_ordinamento_naturale(nome: str):
    """Chiave omogenea per ordinamento naturale di nomi file misti (es. 2.jpg < 10.jpg < p...png)."""
    m = re.match(r'^(\d+)', nome)
    return (0, int(m.group(1)), nome.lower()) if m else (1, 0, nome.lower())


class BuildingContext:
    """Incapsula stato, lock dedicati, persistenza atomica e locandine di un edificio."""

    def __init__(self, config_dict, data_dir):
        self.data_dir = os.path.abspath(data_dir)
        self.config = config_dict if isinstance(config_dict, dict) else {}

        # Gerarchia anti-deadlock e anti-write-skew: lock_disco (RLock) -> lock_memoria (< 1 ms)
        self.lock_config = threading.RLock()
        self.lock_disco = threading.RLock()
        self.lock_memoria = threading.RLock()
        self.lock_locandine = threading.RLock()

        # Stato incapsulato (storico_impegni mutato sempre in-place per aliasing con server_api.py)
        self.storico_impegni = {}
        self.memoria_dati = []
        self.ultimo_sync_cineca_ok = None
        self.ultimo_aggiornamento_preservato = False
        self.ultimo_reset_data = None
        self.ultimo_stato_json_salvato = None

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cartella_locandine(), exist_ok=True)
        self.carica_stato()

    def carica_stato(self) -> bool:
        """Carica stato_impegni.json e ultimo_reset.txt dalla data_dir aggiornando in-place."""
        caricato = False
        file_stato = os.path.join(self.data_dir, 'stato_impegni.json')
        file_reset = os.path.join(self.data_dir, 'ultimo_reset.txt')

        with self.lock_disco:
            if os.path.exists(file_stato):
                try:
                    with open(file_stato, 'r', encoding='utf-8') as f:
                        dati = json.load(f)
                    if isinstance(dati, dict):
                        with self.lock_memoria:
                            self.storico_impegni.clear()
                            self.storico_impegni.update(dati)
                            self.ultimo_stato_json_salvato = json.dumps(
                                self.storico_impegni, indent=4, sort_keys=True
                            )
                        caricato = True
                    else:
                        raise ValueError("Formato stato_impegni.json non dict")
                except Exception as e:
                    logging.warning(f"⚠️ Impossibile leggere stato_impegni.json (file corrotto o non valido): {e}")
                    with self.lock_memoria:
                        self.storico_impegni.clear()
                        self.ultimo_stato_json_salvato = None

            if os.path.exists(file_reset):
                try:
                    with open(file_reset, 'r', encoding='utf-8') as f:
                        val = f.read().strip()
                    self.ultimo_reset_data = val if RE_DATA_RESET.match(val) else None
                except Exception:
                    self.ultimo_reset_data = None

        return caricato

    def aggiorna_impegni(self, nuovo_storico, nuovi_dati=None):
        """Aggiorna in RAM storico impegni (in-place) e dati pubblici sotto lock_memoria."""
        with self.lock_memoria:
            if isinstance(nuovo_storico, dict) and nuovo_storico is not self.storico_impegni:
                self.storico_impegni.clear()
                self.storico_impegni.update(copy.deepcopy(nuovo_storico))
            if nuovi_dati is not None:
                self.memoria_dati = copy.deepcopy(nuovi_dati)

    def ottieni_dati_pubblici(self) -> list[dict]:
        """Restituisce copia difensiva della lista JSON per /dati.json sotto breve lock_memoria."""
        with self.lock_memoria:
            return copy.deepcopy(self.memoria_dati)

    def salva_stato(self, forza=False) -> bool:
        """Persiste stato_impegni.json in modo atomico eseguendo tutto l'I/O FUORI da lock_memoria (ST-09)."""
        with self.lock_disco:
            # Fase 1: Snapshot in RAM (< 1 ms) e rilascio IMMEDIATO di lock_memoria prima di ogni I/O
            with self.lock_memoria:
                nuovo_json = json.dumps(self.storico_impegni, indent=4, sort_keys=True)
                if not forza and nuovo_json == self.ultimo_stato_json_salvato:
                    return False

            # Fase 2: I/O su MicroSD FUORI da lock_memoria (i lettori HTTP non attendono mai fsync)
            percorso_def = os.path.join(self.data_dir, 'stato_impegni.json')
            percorso_tmp = os.path.join(
                self.data_dir, f'stato_impegni_{os.getpid()}_{threading.get_ident()}.tmp'
            )
            try:
                with open(percorso_tmp, 'w', encoding='utf-8') as f:
                    f.write(nuovo_json)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(percorso_tmp, percorso_def)
                with self.lock_memoria:
                    self.ultimo_stato_json_salvato = nuovo_json
                return True
            except Exception as e:
                logging.error(f"❌ Errore durante il salvataggio atomico dello stato: {e}")
                return False
            finally:
                if os.path.exists(percorso_tmp):
                    with contextlib.suppress(OSError):
                        os.remove(percorso_tmp)

    def registra_reset_atomico(self, giorno_op_str: str) -> bool:
        """Scrive ultimo_reset.txt con pattern atomico .tmp + flush + fsync + os.replace (ST-11.1)."""
        file_reset = os.path.join(self.data_dir, 'ultimo_reset.txt')
        file_tmp = os.path.join(
            self.data_dir, f'ultimo_reset_{os.getpid()}_{threading.get_ident()}.tmp'
        )
        with self.lock_disco:
            try:
                with open(file_tmp, 'w', encoding='utf-8') as f:
                    f.write(str(giorno_op_str))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(file_tmp, file_reset)
                return True
            except OSError as e:
                logging.warning(f"⚠️ Impossibile salvare ultimo_reset.txt: {e}")
                return False
            finally:
                if os.path.exists(file_tmp):
                    with contextlib.suppress(OSError):
                        os.remove(file_tmp)

    def verifica_e_esegui_reset_04am(self, dt_roma=None) -> bool:
        """Verifica ed esegue in modo atomico e thread-safe il reset giornaliero delle 04:00 AM."""
        tz_roma = get_tz_roma()
        now_roma = dt_roma or datetime.datetime.now(tz_roma)
        giorno_op_str = str(get_giorno_operativo(now_roma))
        file_reset = os.path.join(self.data_dir, 'ultimo_reset.txt')

        with self.lock_disco:
            if self.ultimo_reset_data is None and os.path.exists(file_reset):
                try:
                    with open(file_reset, 'r', encoding='utf-8') as f:
                        val = f.read().strip()
                    self.ultimo_reset_data = val if RE_DATA_RESET.match(val) else None
                except Exception:
                    self.ultimo_reset_data = None

            if self.ultimo_reset_data != giorno_op_str:
                prec = self.ultimo_reset_data
                logging.info(
                    f"🔄 Esecuzione reset giornaliero impegni "
                    f"(precedente: {prec} -> nuovo giorno operativo: {giorno_op_str})."
                )
                with self.lock_memoria:
                    self.storico_impegni.clear()
                    self.memoria_dati = []
                    self.ultimo_reset_data = giorno_op_str
                self.salva_stato(forza=True)
                self.registra_reset_atomico(giorno_op_str)
                return True
            return False

    # -------------------------------------------------------------------------
    # Pipeline Locandine (D-02, D-03)
    # -------------------------------------------------------------------------

    def cartella_locandine(self) -> str:
        return os.path.join(self.data_dir, 'locandine')

    def percorso_ordine(self) -> str:
        return os.path.join(self.cartella_locandine(), 'ordine.json')

    def leggi_ordine(self) -> list[str]:
        with self.lock_locandine:
            try:
                with open(self.percorso_ordine(), 'r', encoding='utf-8') as f:
                    dati = json.load(f)
            except (OSError, ValueError):
                return []
            return [n for n in dati if isinstance(n, str)] if isinstance(dati, list) else []

    def scrivi_ordine(self, nomi: list[str]):
        with self.lock_locandine:
            cartella = self.cartella_locandine()
            os.makedirs(cartella, exist_ok=True)
            tmp = os.path.join(
                cartella, f'ordine_{os.getpid()}_{threading.get_ident()}.json.tmp'
            )
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(nomi, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.percorso_ordine())
            finally:
                if os.path.exists(tmp):
                    with contextlib.suppress(OSError):
                        os.remove(tmp)

    def elenco_file_locandine(self) -> list[str]:
        with self.lock_locandine:
            cartella = self.cartella_locandine()
            if not os.path.isdir(cartella):
                return []
            nomi = [
                f for f in os.listdir(cartella)
                if not f.startswith('.')
                and f.lower().endswith(ESTENSIONI_LOCANDINE)
                and os.path.isfile(os.path.join(cartella, f))
            ]
            return sorted(nomi, key=chiave_ordinamento_naturale)

    def elenco_locandine_ordinato(self) -> list[str]:
        """Ordine di ordine.json, poi i file non elencati in ordine naturale; voci senza file ignorate."""
        with self.lock_locandine:
            presenti = self.elenco_file_locandine()
            insieme = set(presenti)
            ordinati = [n for n in dict.fromkeys(self.leggi_ordine()) if n in insieme]
            gia = set(ordinati)
            return ordinati + [n for n in presenti if n not in gia]

    def pulisci_upload_orfani(self):
        with self.lock_locandine:
            cartella = self.cartella_locandine()
            if os.path.isdir(cartella):
                for f in os.listdir(cartella):
                    if f.startswith('.upload_') and f.endswith('.tmp'):
                        with contextlib.suppress(OSError):
                            os.remove(os.path.join(cartella, f))

    def salva_locandina_da_stream(self, rfile, content_length: int) -> str:
        """Scrive il body su .tmp a blocchi, valida i magic bytes e rinomina con un nome immutabile."""
        cartella = self.cartella_locandine()
        os.makedirs(cartella, exist_ok=True)
        tmp = os.path.join(cartella, f'.upload_{secrets.token_hex(8)}.tmp')
        testa, letti = b'', 0
        try:
            with open(tmp, 'wb') as f:
                while letti < content_length:
                    blocco = rfile.read(min(65536, content_length - letti))
                    if not blocco:
                        raise ValueError('Upload interrotto prima della fine')
                    if len(testa) < 12:
                        testa += blocco[:12 - len(testa)]
                    f.write(blocco)
                    letti += len(blocco)
                f.flush()
                os.fsync(f.fileno())
            ext = rileva_formato_immagine(testa)
            if not ext:
                raise ValueError('Formato non supportato: ammessi JPEG, PNG, WebP')
            nome = f"p{int(time.time() * 1000)}_{secrets.token_hex(2)}{ext}"
            with self.lock_locandine:
                os.replace(tmp, os.path.join(cartella, nome))
            return nome
        finally:
            if os.path.exists(tmp):
                with contextlib.suppress(OSError):
                    os.remove(tmp)

    def elimina_locandina(self, nome_file: str):
        """Elimina in sicurezza una locandina con validazione anti path-traversal e aggiornamento ordine.json."""
        if (
            not isinstance(nome_file, str)
            or not nome_file
            or '\x00' in nome_file
            or nome_file in ('.', '..')
            or os.path.basename(nome_file) != nome_file
            or '/' in nome_file
            or '\\' in nome_file
        ):
            raise ValueError("Nome file non valido o path traversal rilevato")

        dir_reale = os.path.realpath(self.cartella_locandine())
        percorso_reale = os.path.realpath(os.path.join(dir_reale, nome_file))
        prefisso = dir_reale if dir_reale.endswith(os.sep) else dir_reale + os.sep
        if not percorso_reale.startswith(prefisso):
            raise ValueError("Path traversal rilevato")

        with self.lock_locandine:
            if nome_file not in self.elenco_file_locandine():
                raise ValueError(f"Locandina non trovata: {nome_file}")
            os.remove(percorso_reale)
            self.scrivi_ordine(self.elenco_locandine_ordinato())
            logging.info(f"🗑️ Locandina eliminata: {nome_file}")
