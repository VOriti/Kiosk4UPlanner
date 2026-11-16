"""Hotfix v5.1.12: motore annullamenti CINECA (ST-04 + N-01) e sentinella limite (ST-05)."""
import unittest

from tests._harness import carica_server, chiudi_server, evento, per_id


class TestAnnullamenti(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = carica_server()

    @classmethod
    def tearDownClass(cls):
        chiudi_server(cls.srv)

    def setUp(self):
        self.srv.storico_impegni.clear()
        self.srv.CONFIG.setdefault('api_cineca', {})['id_edificio'] = '05'
        self.srv.CONFIG.setdefault('frontend', {})['mostra_confermati'] = True
        self.giornata = [evento(f'E{i}') for i in range(5)] + [evento('C1', stato='C')]

    def ciclo(self, impegni):
        return per_id(self.srv.estrai_e_formatta_dati(impegni))

    def assertRegolare(self, imp):
        self.assertFalse(imp['cancellato'], imp)
        self.assertEqual(imp['avviso'], '', imp)

    def test_giornata_normale_senza_avvisi(self):
        out = self.ciclo(self.giornata)
        self.assertEqual(len(out), 6)
        for imp in out.values():
            self.assertRegolare(imp)

    def test_assenza_singola_non_annulla(self):
        self.ciclo(self.giornata)
        out = self.ciclo(self.giornata[:1])
        for i in range(1, 5):
            self.assertRegolare(out[f'E{i}'])
            self.assertEqual(out[f'E{i}']['assenze'], 1)

    def test_assenza_confermata_su_due_cicli_annulla(self):
        self.ciclo(self.giornata)
        self.ciclo(self.giornata[:1])
        out = self.ciclo(self.giornata[:1])
        for i in range(1, 5):
            self.assertTrue(out[f'E{i}']['cancellato'])
            self.assertEqual(out[f'E{i}']['avviso'], 'ANNULLATO')
        self.assertRegolare(out['E0'])

    def test_auto_healing_dopo_ritorno_in_cineca(self):
        self.ciclo(self.giornata)
        self.ciclo(self.giornata[:1])
        self.ciclo(self.giornata[:1])
        out = self.ciclo(self.giornata)
        for imp in out.values():
            self.assertRegolare(imp)
            self.assertEqual(imp['assenze'], 0)

    def test_auto_healing_da_sospeso(self):
        self.ciclo([evento('S1', stato='S')])
        out = self.ciclo([evento('S1', stato='P')])
        self.assertRegolare(out['S1'])

    def test_stato_A_annulla_subito(self):
        self.ciclo(self.giornata)
        out = self.ciclo(self.giornata[:5] + [evento('C1', stato='A')])
        self.assertTrue(out['C1']['cancellato'])
        self.assertEqual(out['C1']['avviso'], 'ANNULLATO')

    def test_confermati_nascosti_vengono_rimossi_non_annullati(self):
        self.ciclo(self.giornata)
        self.srv.CONFIG['frontend']['mostra_confermati'] = False
        out = self.ciclo(self.giornata)
        self.assertNotIn('C1', out)
        self.assertNotIn('C1', self.srv.storico_impegni)
        for i in range(5):
            self.assertRegolare(out[f'E{i}'])

    def test_confermati_riattivati_tornano_regolari(self):
        self.ciclo(self.giornata)
        self.srv.CONFIG['frontend']['mostra_confermati'] = False
        self.ciclo(self.giornata)
        self.srv.CONFIG['frontend']['mostra_confermati'] = True
        out = self.ciclo(self.giornata)
        self.assertRegolare(out['C1'])

    def test_cambio_edificio_rimuove_eventi_del_vecchio_edificio(self):
        altro = [evento('X1', edificio='07')]
        self.ciclo(self.giornata + altro)
        self.srv.CONFIG['api_cineca']['id_edificio'] = '07'
        out = self.ciclo(self.giornata + altro)
        self.assertEqual(set(out), {'X1'})
        self.assertRegolare(out['X1'])

    def test_payload_vuoto_preserva_lo_stato(self):
        self.ciclo(self.giornata)
        self.ciclo([])
        out = self.ciclo([])
        self.assertEqual(len(out), 6)
        for imp in out.values():
            self.assertRegolare(imp)
        self.assertTrue(self.srv.ultimo_aggiornamento_preservato)

    def test_evento_illeggibile_non_viene_annullato(self):
        self.ciclo(self.giornata)
        rotto = dict(self.giornata[1])
        del rotto['dataFine']
        with self.assertLogs(level='WARNING') as log:
            self.ciclo([self.giornata[0], rotto] + self.giornata[2:])
            out = self.ciclo([self.giornata[0], rotto] + self.giornata[2:])
        self.assertRegolare(out['E1'])
        self.assertTrue(any('non interpretabile' in riga for riga in log.output))

    def test_descrizione_aula_null_non_scarta_l_evento(self):
        item = evento('N1')
        item['aule'][0]['descrizione'] = None
        out = self.ciclo([item])
        self.assertEqual(out['N1']['aula'], 'Da definire')

    def test_evento_concluso_assente_non_viene_annullato(self):
        self.ciclo([evento('P1', ore_da_ora=-2)] + self.giornata)
        self.ciclo(self.giornata)
        self.ciclo(self.giornata)
        self.assertFalse(self.srv.storico_impegni['P1']['cancellato'])

    def test_sentinella_limite_cineca(self):
        limite = self.srv.LIMITE_EVENTI_CINECA
        with self.assertLogs(level='WARNING') as log:
            self.assertTrue(self.srv.verifica_sentinella_limite([{}] * limite))
        self.assertIn('SENTINELLA LIMITE CINECA', log.output[0])
        self.assertFalse(self.srv.verifica_sentinella_limite([{}] * (limite - 1)))


if __name__ == '__main__':
    unittest.main()
