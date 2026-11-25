"""v5.3.3: BuildingContext, scorporo lock memoria/I/O ST-09, scrittura atomica reset ST-11.1 e locandine."""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from tests._harness import DIR_APP, carica_server, chiudi_server

if DIR_APP not in sys.path:
    sys.path.insert(0, DIR_APP)

from core.building_context import BuildingContext


class TestBuildingContext(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='ctx_v533_')
        self.cfg = {
            'api_cineca': {'id_edificio': '05'},
            'frontend': {'mostra_confermati': True},
        }
        self.ctx = BuildingContext(self.cfg, self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_salva_stato_non_blocca_lock_memoria_durante_fsync_st09(self):
        atteso_pubblico = [{'id': 'E1', 'aula': 'Aula 1'}]
        self.ctx.aggiorna_impegni(
            {'E1': {'id': 'E1', 'aula': 'Aula 1', 'assenze': 0, 'timestamp_fine': time.time() + 3600}},
            nuovi_dati=atteso_pubblico,
        )

        fsync_iniziato = threading.Event()
        sblocca_fsync = threading.Event()
        fsync_originale = os.fsync

        def fsync_lento(fd):
            fsync_iniziato.set()
            sblocca_fsync.wait(timeout=3.0)
            return fsync_originale(fd)

        risultati_scrittura = []

        def thread_scrittura():
            risultati_scrittura.append(self.ctx.salva_stato())

        with mock.patch('core.building_context.os.fsync', side_effect=fsync_lento):
            t_writer = threading.Thread(target=thread_scrittura)
            t_writer.start()
            self.assertTrue(fsync_iniziato.wait(timeout=2.0), 'os.fsync non invocato')

            t0 = time.monotonic()
            dati_pubblici = self.ctx.ottieni_dati_pubblici()
            latenza_lettura = time.monotonic() - t0

            sblocca_fsync.set()
            t_writer.join(timeout=3.0)

        self.assertLess(latenza_lettura, 0.05, f'Letture bloccate da fsync ({latenza_lettura:.3f}s)')
        self.assertIsInstance(dati_pubblici, list)
        self.assertEqual(dati_pubblici, atteso_pubblico)
        self.assertEqual(risultati_scrittura, [True])
        self.assertTrue(os.path.isfile(os.path.join(self.tmpdir, 'stato_impegni.json')))
        residui_tmp = [f for f in os.listdir(self.tmpdir) if f.endswith('.tmp')]
        self.assertEqual(residui_tmp, [])

    def test_salva_stato_condizionale_zero_scritture_se_invariato(self):
        self.ctx.aggiorna_impegni({'E1': {'id': 'E1', 'timestamp_fine': time.time() + 3600}})
        self.assertTrue(self.ctx.salva_stato())
        self.assertFalse(self.ctx.salva_stato(forza=False))
        self.assertTrue(self.ctx.salva_stato(forza=True))

    def test_scrittura_atomica_ultimo_reset_st11_1(self):
        ok = self.ctx.registra_reset_atomico('2026-11-23')
        self.assertTrue(ok)
        file_reset = os.path.join(self.tmpdir, 'ultimo_reset.txt')
        with open(file_reset, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read().strip(), '2026-11-23')

        with mock.patch('core.building_context.os.replace', side_effect=OSError('Blackout simulato')):
            esito_errore = self.ctx.registra_reset_atomico('2026-11-24')
        self.assertFalse(esito_errore)
        with open(file_reset, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read().strip(), '2026-11-23')
        residui_tmp = [f for f in os.listdir(self.tmpdir) if f.endswith('.tmp')]
        self.assertEqual(residui_tmp, [])

    def test_reset_04am_concorrente_eseguito_una_sola_volta(self):
        self.ctx.aggiorna_impegni({'E1': {'id': 'E1', 'timestamp_fine': time.time() + 3600}})
        self.ctx.registra_reset_atomico('2000-01-01')
        self.ctx.ultimo_reset_data = '2000-01-01'
        esiti = []
        barriera = threading.Barrier(4)

        def worker():
            barriera.wait()
            esiti.append(self.ctx.verifica_e_esegui_reset_04am())

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

        self.assertEqual(esiti.count(True), 1)
        self.assertEqual(self.ctx.storico_impegni, {})
        self.assertTrue(os.path.isfile(os.path.join(self.tmpdir, 'ultimo_reset.txt')))

    def test_locandine_ordine_e_path_traversal(self):
        dir_loc = self.ctx.cartella_locandine()
        os.makedirs(dir_loc, exist_ok=True)
        for nome in ('10.jpg', '2.jpg', 'p100_ab12.png'):
            with open(os.path.join(dir_loc, nome), 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 16)

        self.assertEqual(self.ctx.elenco_locandine_ordinato(), ['2.jpg', '10.jpg', 'p100_ab12.png'])
        self.ctx.scrivi_ordine(['p100_ab12.png', 'fantasma.jpg', '2.jpg'])
        self.assertEqual(self.ctx.elenco_locandine_ordinato(), ['p100_ab12.png', '2.jpg', '10.jpg'])
        with self.assertRaises(ValueError):
            self.ctx.elimina_locandina('../../etc/passwd')

    def test_harness_verifica_integrazione_context(self):
        srv = carica_server()
        try:
            self.assertTrue(hasattr(srv, 'salva_stato'))
            self.assertTrue(hasattr(srv, 'verifica_e_esegui_reset_04am'))
        finally:
            chiudi_server(srv)


if __name__ == '__main__':
    unittest.main()
