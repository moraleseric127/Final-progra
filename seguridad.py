"""Contraseña propia, configuración privada y sesiones persistentes del taller."""
import hashlib  # Deriva una huella costosa; no almacena la contraseña original.
import hmac  # Compara las huellas sin abandonar al primer carácter distinto.
import json  # Guarda la configuración local fuera del código fuente.
import os  # Lee los secretos del alojamiento cuando se publica.
import secrets  # Crea sales y tokens criptográficamente aleatorios.
import time  # Expira sesiones e intentos utilizando segundos UTC.
import core  # Reutiliza la carpeta de datos y las transacciones SQLite.


def hash_password(password):  # Genera una huella portable sin bibliotecas adicionales.
    if not isinstance(password, str) or not 12 <= len(password) <= 128:  # Evita claves cortas o entradas excesivas.
        raise ValueError('Usa una contraseña de 12 a 128 caracteres.')  # La clave se elige fuera del chat.
    salt = secrets.token_hex(16)  # Cada configuración obtiene una sal independiente.
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000)  # Hace costosos los intentos masivos.
    return 'pbkdf2_sha256$600000$' + salt + '$' + digest.hex()  # No contiene la contraseña original.


def verify_password(password, encoded):  # Valida en el servidor, nunca en JavaScript.
    try:  # Una configuración dañada no debe conceder acceso.
        algorithm, rounds, salt, expected = encoded.split('$')  # Recupera parámetros públicos de la derivación.
        if algorithm != 'pbkdf2_sha256' or not 100000 <= int(rounds) <= 1000000 or len(str(password)) > 128:  # Acota el trabajo.
            return False  # Rechaza formatos inesperados.
        digest = hashlib.pbkdf2_hmac('sha256', str(password).encode(), bytes.fromhex(salt), int(rounds))  # Recalcula la huella.
        return hmac.compare_digest(digest.hex(), expected)  # No compara contraseñas en texto claro.
    except (ValueError, TypeError):  # Maneja configuración incompleta o valores inválidos.
        return False  # Fallo cerrado.


def load_hash():  # Prefiere el secreto del servidor a la configuración local.
    value = os.environ.get('YONKESITO_PASSWORD_HASH')  # El alojamiento no necesita la clave en texto claro.
    if value:  # El proveedor inyecta esta variable privada.
        return value  # No se devuelve al navegador.
    path = core.ROOT / 'acceso.json'  # Se excluye de ZIP y Git.
    if path.exists():  # La primera ejecución requiere configurar la clave.
        return json.loads(path.read_text(encoding='utf-8'))['password_hash']  # Lee solo la huella.
    raise RuntimeError('Primero ejecuta configurar_acceso.py y define la contraseña del taller.')  # Instrucción recuperable.


def initialize():  # Crea almacenamiento de autenticación sin introducir piezas.
    with core.connection() as db:  # Transacción y cierre automático.
        db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL)')  # Tokens se guardan como hash.
        db.execute('CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT PRIMARY KEY, count INTEGER NOT NULL, until REAL NOT NULL)')  # Límite persistente de intentos.


def token_hash(token):  # Un volcado de la base no debe revelar cookies utilizables.
    return hashlib.sha256(token.encode()).hexdigest()  # La cookie real tiene 256 bits aleatorios.


def reserve_attempt(ip):  # Limita a cinco intentos por dirección cada quince minutos.
    now = time.time()  # Evita depender de la fecha declarada por el usuario.
    with core.connection() as db:  # Comparte límite entre reinicios y solicitudes.
        db.execute('BEGIN IMMEDIATE')  # Serializa comprobación y actualización.
        db.execute('DELETE FROM login_attempts WHERE until <= ?', (now,))  # Limpia ventanas vencidas.
        row = db.execute('SELECT count FROM login_attempts WHERE ip=?', (ip,)).fetchone()  # IP proporcionada por el servidor.
        if row and row['count'] >= 5:  # No intenta derivar otra contraseña durante el bloqueo.
            return False  # La interfaz devuelve HTTP 429.
        db.execute('INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(ip) DO UPDATE SET count=count+1', (ip, now + 900))  # Incremento atómico.
        return True  # Permite comprobar esta contraseña.


def clear_attempts(ip):  # Un ingreso correcto cancela los errores anteriores de esa dirección.
    with core.connection() as db:  # Confirmación automática al terminar.
        db.execute('DELETE FROM login_attempts WHERE ip=?', (ip,))  # No afecta a otros visitantes.


def new_session(name, date, password_hash):  # Crea sesión de ocho horas con rol fijado por el servidor.
    token = secrets.token_urlsafe(32)  # Nunca se acepta el identificador enviado por el formulario.
    value = {'name': name, 'date': date, 'role': 'staff', 'csrf': secrets.token_urlsafe(32), 'revision': token_hash(password_hash)}  # Vincula la sesión a la clave vigente.
    with core.connection() as db:  # Guarda sin revelar el token de la cookie.
        db.execute('DELETE FROM sessions WHERE expires <= ?', (time.time(),))  # Limpia sesiones caducadas.
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (token_hash(token), json.dumps(value), time.time() + 28800))  # Límite absoluto de ocho horas.
    return token, value  # Solo la respuesta HTTP recibe el token original.


def get_session(token, password_hash):  # Toda operación interna vuelve a verificar permisos.
    with core.connection() as db:  # Consulta parametrizada.
        row = db.execute('SELECT payload FROM sessions WHERE token=? AND expires>?', (token_hash(token), time.time())).fetchone()  # Rechaza expiración.
    if not row:  # Un cliente anónimo no tiene una sesión válida.
        return None  # El catálogo público sigue funcionando.
    value = json.loads(row['payload'])  # Solo datos generados por este módulo.
    if value.get('revision') != token_hash(password_hash):  # Cambiar la contraseña invalida accesos anteriores.
        return None  # Obliga a autenticarse otra vez.
    value['date'] = tuple(value['date'])  # Restaura explícitamente la tupla de la rúbrica.
    return value  # Nunca depende del rol indicado por el navegador.


def revoke(token):  # Cierra realmente la sesión del servidor.
    with core.connection() as db:  # También funciona después de un reinicio.
        db.execute('DELETE FROM sessions WHERE token=?', (token_hash(token),))  # Impide reutilizar la cookie cerrada.
