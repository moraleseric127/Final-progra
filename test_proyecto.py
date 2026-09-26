"""Pruebas de depuración aisladas: python -m unittest -v test_proyecto.py."""
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest
import core
import consola


class ProjectTests(unittest.TestCase):
    def setUp(self):
        # Cada caso trabaja en una carpeta temporal; nunca cambia el inventario real.
        self.temp = TemporaryDirectory()
        self.root, self.docs = core.ROOT, core.DOCS
        core.ROOT = Path(self.temp.name)
        core.DOCS = core.ROOT / 'documentos'
        core.initialize()
        self.assertEqual(core.inventory(), [])
        self.fixture = {'code':'MOT-001','name':'Pieza de prueba','category':'Motor','vehicle':'Aplicación de prueba','condition':'Usada','quantity':6,'minimum':2,'price':'150.25'}
        core.add_part(self.fixture, (23,9,2026), 'Pruebas')
        core.add_part(dict(self.fixture, code='SUS-004', quantity=1), (23,9,2026), 'Pruebas')
        self.date = core.date_tuple('23/09/2026')

    def tearDown(self):
        # Devuelve la configuración original después de cada prueba.
        core.ROOT, core.DOCS = self.root, self.docs
        self.temp.cleanup()

    def test_date_tuple_and_invalid_calendar(self):
        self.assertEqual(self.date, (23, 9, 2026))
        for value in ['31/02/2026', '2026-09-23', '1/1/2026']:
            with self.assertRaises(ValueError):
                core.date_tuple(value)

    def test_four_documents_and_missing_file(self):
        self.assertEqual(len(core.documents()), 4)
        self.assertIn('El Yonkesito', core.read_document('bienvenida.txt'))
        with self.assertRaises(FileNotFoundError):
            core.read_document('ausente.txt')

    def test_document_creation_update_date_and_duplicate(self):
        core.write_document('prueba.txt', 'Texto inicial', self.date, 'Eric', True)
        with self.assertRaises(FileExistsError):
            core.write_document('prueba.txt', 'Otra captura', self.date, 'Eric', True)
        old = core.read_document('prueba.txt')
        core.write_document('prueba.txt', old + 'Revisado', (24, 9, 2026), 'Eric')
        result = core.read_document('prueba.txt')
        self.assertIn('24/09/2026', result)
        self.assertEqual(result.count('Fecha:'), 1)
        self.assertIn('Revisado', result)

    def test_paths_and_quantities_rejected(self):
        for name in ['../app.py', 'otro/archivo.txt', 'mal escrito.txt']:
            with self.assertRaises(ValueError):
                core.read_document(name)
        for value in ['-1', '1.5', 'abc', '10000000']:
            with self.assertRaises(ValueError):
                core.integer(value, 'Cantidad')

    def test_entry_exit_and_stock_guard(self):
        data = {'code': 'MOT-001', 'kind': 'Entrada', 'amount': 2, 'note': 'Recepción'}
        self.assertEqual(core.move(data, self.date, 'Eric'), 8)
        data.update(kind='Salida', amount=6)
        self.assertEqual(core.move(data, self.date, 'Eric'), 2)
        self.assertEqual(core.history()[0]['date'], '23/09/2026')
        data['amount'] = 3
        with self.assertRaises(ValueError):
            core.move(data, self.date, 'Eric')
        self.assertEqual(next(p for p in core.inventory() if p['code']=='MOT-001')['quantity'], 2)

    def test_duplicate_code_and_persistence(self):
        data = dict(self.fixture)
        with self.assertRaises(ValueError):
            core.add_part(data, self.date, 'Eric')
        data['code'] = 'NUE-009'
        core.add_part(data, self.date, 'Eric')
        core.initialize()
        self.assertEqual(len(core.inventory()), 3)

    def test_concurrent_dispatch_keeps_stock_nonnegative(self):
        def dispatch():
            try:
                core.move({'code':'SUS-004','kind':'Salida','amount':1,'note':'Prueba'},self.date,'Eric')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(lambda _:dispatch(), range(2)))
        self.assertEqual(sum(result), 1)

    def test_price_precision_and_validation(self):
        self.assertEqual(core.price_cents('125.05'), 12505)
        self.assertEqual(core.price_cents('0'), 0)
        for value in ['', '-1', '1.555', 'NaN', 'Infinity', '1e2']:
            with self.assertRaises(ValueError):
                core.price_cents(value)
        core.set_price({'code':'MOT-001','price':'99.90'})
        self.assertEqual(next(p for p in core.inventory() if p['code']=='MOT-001')['price_cents'],9990)

    def test_timer_continue_and_change_without_ten_minute_wait(self):
        # Se acorta solo el parámetro de prueba; producción conserva 600 segundos.
        with patch('consola.ask', return_value='sí'):
            self.assertEqual(consola.timed_option(seconds=0), 'continue')
        with patch('consola.ask', return_value='no'):
            self.assertEqual(consola.timed_option(seconds=0), 'change')
        consola.INPUT.put('5')
        self.assertEqual(consola.timed_option(seconds=1), '5')


if __name__ == '__main__':
    unittest.main()
