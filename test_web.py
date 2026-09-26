"""Pruebas HTTP aisladas: autenticación, permisos y persistencia."""
from pathlib import Path  # Rutas temporales compatibles con Windows.
from tempfile import TemporaryDirectory  # No toca datos reales.
import unittest  # Ejecución reproducible de casos.
import core  # Reglas compartidas.
import seguridad  # Contraseñas y sesiones.
from app import create_app  # Cliente HTTP de prueba de Flask.


class WebTests(unittest.TestCase):  # Casos de comportamiento observable.
    @classmethod  # Deriva una clave sintética por conjunto.
    def setUpClass(cls):  # No es una contraseña predeterminada del programa.
        cls.password = 'Solo-Pruebas-12345'  # Exclusiva de pruebas temporales.
        cls.encoded = seguridad.hash_password(cls.password)  # Derivación aleatoria.

    def setUp(self):  # Un inventario limpio por caso.
        self.temp = TemporaryDirectory()  # Directorio desechable.
        self.previous = core.ROOT, core.DOCS  # Respalda rutas.
        core.ROOT = Path(self.temp.name)  # Aísla base.
        core.DOCS = core.ROOT / 'documentos'  # Aísla archivos.
        self.app = create_app({'TESTING': True, 'PASSWORD_HASH': self.encoded})  # Sin secretos reales.
        self.client = self.app.test_client()  # Conserva cookies de prueba.
        self.part = dict(code='PRU-1', name='Pieza temporal', category='Motor', vehicle='Vehículo de prueba', condition='Usada', quantity=2, minimum=1, price='125.05')  # No se distribuye como dato.
        self.headers = {'Origin': 'http://localhost'}  # Origen legítimo.

    def tearDown(self):  # Restaura configuración anterior.
        core.ROOT, core.DOCS = self.previous  # Datos reales intactos.
        self.temp.cleanup()  # Borra solo el entorno de prueba.

    def login(self):  # Ingresa con nombre, fecha y clave.
        result = self.client.post('/api/login', json={'name':'Pruebas', 'date':'24/09/2026', 'password':self.password}, headers=self.headers)  # Formulario completo.
        self.assertEqual(result.status_code, 200)  # Acceso correcto.
        self.headers['X-CSRF-Token'] = result.json['session']['csrf']  # Token recibido del servidor.
        return result  # Permite revisar cookie.

    def test_empty_public_catalog_and_denied_edits(self):  # Solo inventario público.
        self.assertEqual(self.client.get('/api/inventory').json, {'items': []})  # Sin piezas precargadas.
        for endpoint in ('parts', 'price', 'move', 'retire'):  # Cada escritura requiere sesión.
            self.assertEqual(self.client.post('/api/'+endpoint, json={'role':'staff'}, headers=self.headers).status_code, 401)  # Rol inventado no sirve.
        self.assertEqual(self.client.get('/api/documents').status_code, 401)  # Documentos protegidos.
        self.assertEqual(self.client.get('/datos/acceso.json').status_code, 404)  # Secretos inaccesibles.

    def test_password_limit_and_wrong_origin(self):  # Cinco intentos cada quince minutos.
        for _ in range(5):  # Verifica el límite sin esperas reales.
            self.assertEqual(self.client.post('/api/login', json={'password':'incorrecta'}, headers=self.headers).status_code, 403)  # Clave inválida.
        self.assertEqual(self.client.post('/api/login', json={'password':self.password}, headers=self.headers).status_code, 429)  # Sexto bloqueado.
        self.assertEqual(self.client.post('/api/login', json={}, headers={'Origin':'https://ajeno.example'}).status_code, 403)  # Origen ajeno rechazado.

    def test_staff_price_movement_and_public_filter(self):  # Flujo principal completo.
        self.login()  # Obtiene sesión legítima.
        self.assertEqual(self.client.post('/api/parts', json=self.part, headers=self.headers).status_code, 200)  # Alta individual.
        self.assertEqual(self.client.post('/api/price', json={'code':'PRU-1','price':'199.90'}, headers=self.headers).status_code, 200)  # Modifica precio.
        guest = self.app.test_client()  # Visitante independiente.
        record = guest.get('/api/inventory').json['items'][0]  # Lectura pública.
        self.assertEqual(record['price_cents'], 19990)  # Centavos exactos.
        self.assertNotIn('minimum', record)  # Umbral interno oculto.
        move = dict(code='PRU-1', kind='Salida', amount=2, note='Prueba')  # Agota la pieza temporal.
        self.assertEqual(self.client.post('/api/move', json=move, headers=self.headers).status_code, 200)  # Salida válida.
        self.assertEqual(guest.get('/api/inventory').json['items'], [])  # Agotada no es pública.
        self.assertEqual(self.client.post('/api/move', json=move, headers=self.headers).status_code, 400)  # Sin saldo negativo.

    def test_csrf_logout_and_restart(self):  # Persistencia y revocación real.
        self.login()  # Captura sesión.
        cookie = self.client.get_cookie('session').value  # Cookie sintética.
        self.assertEqual(self.client.post('/api/parts', json=self.part, headers={'Origin':'http://localhost'}).status_code, 403)  # Sin CSRF se rechaza.
        restarted = create_app({'TESTING':True,'PASSWORD_HASH':self.encoded}).test_client()  # Simula reinicio.
        restarted.set_cookie('session', cookie)  # Mismo navegador.
        self.assertEqual(restarted.get('/api/session').json['session']['role'], 'staff')  # Sesión persistida.
        self.assertEqual(self.client.post('/api/logout', json={}, headers=self.headers).status_code, 200)  # Cierre en servidor.
        self.assertEqual(restarted.get('/api/session').json['session']['role'], 'client')  # Cookie anterior ya no sirve.

    def test_retire_permissions_confirmation_and_persistence(self):
        self.login()
        self.client.post('/api/parts', json=self.part, headers=self.headers)
        data = dict(code='PRU-1', note='Descontinuada', confirm='PRU-1')
        guest = self.app.test_client()
        self.assertEqual(guest.post('/api/retire', json=data, headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/api/retire', json=data, headers={'Origin':'http://localhost'}).status_code, 403)
        self.assertEqual(self.client.post('/api/retire', json={**data, 'confirm':'NO'}, headers=self.headers).status_code, 400)
        self.assertEqual(len(core.inventory()), 1)
        self.assertEqual(self.client.post('/api/retire', json=data, headers=self.headers).status_code, 200)
        core.initialize()
        self.assertEqual(core.inventory(), [])
        self.assertEqual(guest.get('/api/inventory').json['items'], [])
        self.assertEqual(core.history()[0]['kind'], 'Baja')
        self.assertEqual(len(core.history()), 2)
        self.assertEqual(self.client.post('/api/retire', json=data, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/price', json={'code':'PRU-1','price':'5'}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/move', json={'code':'PRU-1','kind':'Entrada','amount':1,'note':'x'}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get('/api/documents').status_code, 404)
        self.assertEqual(self.client.post('/api/document', json={}, headers=self.headers).status_code, 404)

    def test_migration_preserves_existing_inventory(self):
        with core.connection() as db:
            db.execute('DROP TABLE parts')
            db.execute('CREATE TABLE parts (code TEXT PRIMARY KEY, name TEXT, quantity INTEGER, minimum INTEGER, price_cents INTEGER)')
            db.execute("INSERT INTO parts VALUES ('OLD','Anterior',0,1,123)")
        core.initialize()
        self.assertEqual(core.inventory()[0]['active'], 1)
        self.assertEqual(core.inventory()[0]['price_cents'], 123)

    def test_password_rotation_and_https_cookie(self):  # Protecciones de alojamiento.
        self.app.config['SECURE_COOKIE'] = True  # HTTPS configurado.
        result = self.login()  # Cookie emitida.
        self.assertIn('Secure;', result.headers['Set-Cookie'])  # Solo HTTPS.
        self.assertIn('HttpOnly;', result.headers['Set-Cookie'])  # JS no puede leerla.
        self.app.config['PASSWORD_HASH'] = seguridad.hash_password('Otra-Clave-Prueba-123')  # Rota clave.
        self.assertEqual(self.client.get('/api/session').json['session']['role'], 'client')  # Sesiones anteriores inválidas.


if __name__ == '__main__':  # También ejecutable desde PyCharm.
    unittest.main()  # Devuelve fallo si un caso no cumple.
