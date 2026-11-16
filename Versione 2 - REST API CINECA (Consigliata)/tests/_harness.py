"""Harness condiviso: carica server_api.py da una COPIA in una cartella temporanea.

All'import server_api.py legge o crea config.yaml, stato_impegni.json, ultimo_reset.txt e kiosk.log
nella propria cartella: lavorando su una copia i test non toccano mai i file reali del kiosk.
"""
import datetime
import importlib.util
import itertools
import logging
import os
import shutil
import tempfile
import threading
import urllib.error
import urllib.request

DIR_APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dashboard_aule'))
FILE_STATICI = ('remoto.html', 'admin.html', 'logo.png')
_contatore = itertools.count()


def carica_server(con_locandine=False):
    tmp = tempfile.mkdtemp(prefix='kiosk_test_')
    shutil.copy(os.path.join(DIR_APP, 'server_api.py'), tmp)
    for nome in FILE_STATICI:
        sorgente = os.path.join(DIR_APP, nome)
        if os.path.exists(sorgente):
            shutil.copy(sorgente, tmp)
    os.makedirs(os.path.join(tmp, 'locandine'), exist_ok=True)
    if con_locandine:
        cartella = os.path.join(DIR_APP, 'locandine')
        for nome in os.listdir(cartella):
            shutil.copy(os.path.join(cartella, nome), os.path.join(tmp, 'locandine'))
    spec = importlib.util.spec_from_file_location(
        f'server_api_test_{next(_contatore)}', os.path.join(tmp, 'server_api.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._tmpdir = tmp
    return mod


def chiudi_server(mod):
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    shutil.rmtree(mod._tmpdir, ignore_errors=True)


def avvia_http(mod):
    """Avvia KioskServer su una porta libera di 127.0.0.1. Ritorna (base_url, httpd)."""
    httpd = mod.KioskHTTPServer(('127.0.0.1', 0), mod.KioskServer)
    httpd.is_ssl = False
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{httpd.server_address[1]}', httpd


def ferma_http(httpd):
    httpd.shutdown()
    httpd.server_close()


def richiesta(url, metodo='GET', corpo=None, header=None):
    """Ritorna (status, header_risposta, corpo_bytes) senza sollevare eccezioni sugli HTTP 4xx/5xx."""
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=header or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def evento(id_imp, stato='P', ore_da_ora=2, durata_ore=1, aula='Aula 1', edificio='05', **extra):
    """Impegno nel formato grezzo restituito da getImpegniCalendario."""
    inizio = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ore_da_ora)
    fine = inizio + datetime.timedelta(hours=durata_ore)
    item = {
        'id': id_imp, 'stato': stato, 'nome': f'Lezione {id_imp}',
        'dataInizio': inizio.isoformat(), 'dataFine': fine.isoformat(),
        'aule': [{'descrizione': aula, 'edificio': {'codice': edificio}}],
    }
    item.update(extra)
    return item


def per_id(dati_puliti):
    return {imp['id']: imp for imp in dati_puliti}
