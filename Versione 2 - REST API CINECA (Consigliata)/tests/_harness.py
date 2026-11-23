"""Harness condiviso: carica server_api.py da una COPIA in una cartella temporanea.

All'import server_api.py legge o crea config.yaml, stato_impegni.json, ultimo_reset.txt e kiosk.log
nella propria cartella: lavorando su una copia i test non toccano mai i file reali del kiosk.
Salva e ripristina sys.path e sys.modules['core*'] per non invalidare i riferimenti di @mock.patch.
"""
import datetime
import hashlib
import http.client
import importlib.util
import itertools
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

DIR_APP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dashboard_aule'))
FILE_STATICI = (
    'remoto.html',
    'admin.html',
    os.path.join('static', 'remoto.js'),
    os.path.join('static', 'admin.js'),
    os.path.join('static', 'remoto.css'),
    os.path.join('static', 'admin.css'),
    'logo.png',
    'config.example.yaml',
)
_contatore = itertools.count()


def carica_server(con_locandine=False):
    tmp = tempfile.mkdtemp(prefix='kiosk_test_')
    shutil.copy(os.path.join(DIR_APP, 'server_api.py'), tmp)
    dir_core_src = os.path.join(DIR_APP, 'core')
    if os.path.isdir(dir_core_src):
        shutil.copytree(
            dir_core_src,
            os.path.join(tmp, 'core'),
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'),
        )
    dir_static_src = os.path.join(DIR_APP, 'static')
    if os.path.isdir(dir_static_src):
        shutil.copytree(
            dir_static_src,
            os.path.join(tmp, 'static'),
            dirs_exist_ok=True,
        )
    for nome in FILE_STATICI:
        sorgente = os.path.join(DIR_APP, nome)
        if os.path.exists(sorgente):
            destinazione = os.path.join(tmp, nome)
            os.makedirs(os.path.dirname(destinazione), exist_ok=True)
            shutil.copy(sorgente, destinazione)
    os.makedirs(os.path.join(tmp, 'locandine'), exist_ok=True)
    if con_locandine:
        cartella = os.path.join(DIR_APP, 'locandine')
        if os.path.isdir(cartella):
            for nome in os.listdir(cartella):
                sorgente_loc = os.path.join(cartella, nome)
                if os.path.isfile(sorgente_loc):
                    shutil.copy(sorgente_loc, os.path.join(tmp, 'locandine'))

    prev_core_modules = {
        k: v for k, v in list(sys.modules.items())
        if k == 'core' or k.startswith('core.')
    }
    for k in prev_core_modules:
        sys.modules.pop(k, None)

    sys.path.insert(0, tmp)
    spec = importlib.util.spec_from_file_location(
        f'server_api_test_{next(_contatore)}', os.path.join(tmp, 'server_api.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._tmpdir = tmp
    mod._prev_core_modules = prev_core_modules
    return mod


def chiudi_server(mod):
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    if hasattr(mod, '_tmpdir') and mod._tmpdir in sys.path:
        sys.path.remove(mod._tmpdir)
    for k in [k for k in list(sys.modules) if k == 'core' or k.startswith('core.')]:
        sys.modules.pop(k, None)
    for k, v in getattr(mod, '_prev_core_modules', {}).items():
        sys.modules[k] = v
    shutil.rmtree(getattr(mod, '_tmpdir', ''), ignore_errors=True)


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
        with e:
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


PASSWORD_TEST = 'password-di-test-kiosk'
JPEG_MINIMO = b'\xff\xd8\xff\xe0' + b'\x00' * 64
PNG_MINIMO = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
WEBP_MINIMO = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'\x00' * 64


def login_admin(mod, base):
    sic = mod.CONFIG.setdefault('sicurezza', {})
    sic.update({'admin_attivo': True, 'admin_ip_autorizzati': [],
                'password_admin_hash': hashlib.sha256(PASSWORD_TEST.encode()).hexdigest()})
    status, _, corpo = richiesta(base + '/api/admin/login', 'POST',
                                 json.dumps({'password': PASSWORD_TEST}).encode(),
                                 {'Content-Type': 'application/json'})
    assert status == 200, corpo
    return json.loads(corpo)['token']


def post_grezzo(base, percorso, header, corpo=b''):
    """POST con header scritti a mano (per Content-Length malformati). Ritorna (status, corpo)."""
    u = urllib.parse.urlparse(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    conn.putrequest('POST', percorso, skip_accept_encoding=True)
    for chiave, valore in header:
        conn.putheader(chiave, valore)
    conn.endheaders()
    if corpo:
        conn.send(corpo)
    risposta = conn.getresponse()
    esito = (risposta.status, risposta.read())
    conn.close()
    return esito
