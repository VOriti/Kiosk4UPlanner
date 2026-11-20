"""Esegue in Node.js funzioni JavaScript estratte dalle pagine HTML (test di comportamento del frontend)."""
import json
import os
import re
import shutil
import subprocess
import tempfile

from tests._harness import DIR_APP

NODE = shutil.which('node')


def estrai_funzione_js(nome_file, nome_funzione):
    """Ritorna il sorgente completo di `function nome(...) {...}` (anche async) contando le graffe."""
    with open(os.path.join(DIR_APP, nome_file), encoding='utf-8') as f:
        sorgente = f.read()
    m = re.search(r'(async\s+)?function\s+' + re.escape(nome_funzione) + r'\s*\(', sorgente)
    if not m:
        raise AssertionError(f'funzione {nome_funzione} non trovata in {nome_file}')
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


def esegui_js(nome_file, funzioni, espressione, prologo=''):
    """Definisce `funzioni` (estratte da nome_file), valuta `espressione` e ne ritorna il valore JSON."""
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
    with open(os.path.join(DIR_APP, nome_file), encoding='utf-8') as f:
        return f.read()
