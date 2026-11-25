"""Esegue in Node.js funzioni JavaScript estratte dalle pagine HTML o dai file JS in static/ estratti in v5.3.5."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from tests._harness import DIR_APP

NODE = shutil.which('node')


def _sorgenti_candidati(nome_file):
    """Restituisce i contenuti del file richiesto (anche cercando in static/) e degli eventuali .js/.css omonimi in static/."""
    percorso_principale = os.path.join(DIR_APP, nome_file)
    contenuti = []
    if os.path.isfile(percorso_principale):
        with open(percorso_principale, encoding='utf-8') as f:
            contenuti.append(f.read())
    else:
        percorso_static = os.path.join(DIR_APP, 'static', os.path.basename(nome_file))
        if os.path.isfile(percorso_static):
            with open(percorso_static, encoding='utf-8') as f:
                contenuti.append(f.read())
    base, ext = os.path.splitext(os.path.basename(nome_file))
    if ext.lower() == '.html':
        for extra_ext in ('.js', '.css'):
            for cartella in (os.path.join(DIR_APP, 'static'), DIR_APP):
                percorso_extra = os.path.join(cartella, base + extra_ext)
                if os.path.isfile(percorso_extra):
                    with open(percorso_extra, encoding='utf-8') as f:
                        contenuti.append(f.read())
                    break
    return contenuti


def estrai_funzione_js(nome_file, nome_funzione):
    """Ritorna il sorgente completo di `function nome(...) {...}` (anche async) contando le graffe."""
    pattern = re.compile(r'(async\s+)?function\s+' + re.escape(nome_funzione) + r'\s*\(')
    for sorgente in _sorgenti_candidati(nome_file):
        m = pattern.search(sorgente)
        if not m:
            continue
        apertura = sorgente.index('{', m.end())
        profondita = 0
        for i in range(apertura, len(sorgente)):
            if sorgente[i] == '{':
                profondita += 1
            elif sorgente[i] == '}':
                profondita -= 1
                if profondita == 0:
                    return sorgente[m.start():i + 1]
        raise AssertionError(f'graffe non bilanciate in {nome_funzione}')
    raise AssertionError(f'funzione {nome_funzione} non trovata in {nome_file}')


def esegui_js(nome_file, funzioni, espressione, prologo=''):
    """Definisce `funzioni` (estratte da nome_file o static/*.js associato), valuta `espressione` e ne ritorna il JSON."""
    if not NODE:
        raise RuntimeError("Node.js non trovato nel PATH di sistema")
    codice = prologo + '\n' + '\n'.join(estrai_funzione_js(nome_file, f) for f in funzioni)
    codice += f'\nprocess.stdout.write(JSON.stringify({espressione}));\n'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tmp:
        tmp.write(codice)
    try:
        esito = subprocess.run([NODE, tmp.name], capture_output=True, text=True, timeout=30)
    finally:
        os.remove(tmp.name)
    if esito.returncode != 0:
        raise AssertionError(esito.stderr)
    return json.loads(esito.stdout)


def leggi_pagina(nome_file):
    """Legge il file HTML e concatena eventuali static/*.js e static/*.css omonimi per retrocompatibilità coi test v5.2."""
    return '\n'.join(_sorgenti_candidati(nome_file))
