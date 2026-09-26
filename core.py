"""Reglas compartidas por la web y la consola de El Yonkesito."""
from contextlib import contextmanager  # Cierra conexiones tras confirmar o revertir.
from datetime import datetime  # Valida fechas reales, incluidos años bisiestos.
from pathlib import Path  # Construye rutas compatibles con Windows y otros sistemas.
import os  # Lee configuración opcional sin editar el programa.
import re  # Comprueba formatos de códigos, fechas y nombres de archivo.
import sqlite3  # Persiste el inventario con transacciones incluidas en Python.
import threading  # Coordina las escrituras de documentos entre solicitudes.

# La carpeta se puede cambiar para ejecutar pruebas sin tocar los datos reales.
ROOT = Path(os.environ.get('YONKESITO_DATA', Path(__file__).parent / 'datos'))
DOCS = ROOT / 'documentos'
LOCK = threading.RLock()  # Impide escrituras simultáneas dentro de este proceso.
STATES = ('Usada', 'Nueva', 'Reacondicionada')  # Condiciones admitidas por el catálogo.

@contextmanager  # Garantiza el cierre de SQLite en todas las operaciones.
def connection():  # Centraliza la apertura de la base de datos.
    # sqlite3 abre transacciones para que una salida no deje stock negativo.
    db = sqlite3.connect(ROOT / 'inventario.sqlite3', timeout=10)
    db.row_factory = sqlite3.Row  # Las filas se convierten fácilmente a diccionarios.
    try:  # El bloque with de SQLite confirma o revierte automáticamente.
        with db:  # Agrupa las operaciones de quien utiliza esta conexión.
            yield db  # Entrega temporalmente la conexión al modelo.
    finally:  # También se ejecuta ante errores de validación o escritura.
        db.close()  # Libera el descriptor sin depender del recolector de basura.


def initialize():  # Prepara almacenamiento, tablas y documentos de la primera ejecución.
    # Nunca se reemplazan registros que el usuario ya haya capturado.
    DOCS.mkdir(parents=True, exist_ok=True)  # Permite reiniciar sin fallar si ya existe la carpeta.
    with connection() as db:  # Confirma la transacción al terminar o revierte ante un error.
        db.execute('CREATE TABLE IF NOT EXISTS parts (code TEXT PRIMARY KEY, name TEXT, category TEXT, vehicle TEXT, condition TEXT, quantity INTEGER CHECK(quantity>=0), minimum INTEGER CHECK(minimum>=0))')  # Los CHECK protegen las cantidades incluso fuera de la interfaz.
        db.execute('CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY, code TEXT, kind TEXT, amount INTEGER, date TEXT, user TEXT, note TEXT)')  # Registra una bitácora separada del saldo actual.
        db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')  # Guarda la marca de inicialización del catálogo.
        # Las instalaciones nuevas empiezan vacías; bases existentes conservan sus piezas.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(parts)')}
        if 'active' not in columns:
            db.execute('ALTER TABLE parts ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        if 'price_cents' not in columns:
            db.execute('ALTER TABLE parts ADD COLUMN price_cents INTEGER CHECK(price_cents>=0)')
    # Estos cuatro archivos están disponibles antes de iniciar la sesión.
    initial = {  # Diccionario de cuatro archivos de lectura preexistentes.
        'bienvenida.txt': 'El Yonkesito: control de refacciones. Registra las piezas del taller una por una antes de consultar el catálogo.',
        'recepcion.txt': 'Recepción: verificar código, aplicación, condición y cantidad antes de registrar una entrada.',
        'despacho.txt': 'Despacho: verificar compatibilidad y registrar una salida; no entregar más unidades que las disponibles.',
        'reposicion.txt': 'Reposición: revisar las piezas cuya cantidad sea menor o igual al stock mínimo.',
    }
    for name, content in initial.items():  # Recorre nombres y textos de los documentos de ejemplo.
        path = DOCS / name  # Las claves son nombres internos y seguros.
        if not path.exists():  # Comprueba la existencia antes de operar sobre el archivo.
            path.write_text(content + '\n', encoding='utf-8')  # Guarda texto Unicode para conservar acentos.


def date_tuple(value):  # Convierte una fecha capturada en la tupla de la rúbrica.
    # La expresión exige el formato de la rúbrica; datetime valida el calendario.
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', str(value)):  # Rechaza fechas que no tengan dos dígitos para día y mes.
        raise ValueError('Escribe la fecha como dd/mm/aaaa.')  # La interfaz mostrará el formato correcto al usuario.
    date = datetime.strptime(value, '%d/%m/%Y')  # Rechaza fechas imposibles, como el 31 de febrero.
    return (date.day, date.month, date.year)  # Tupla: día, mes, año.


def date_text(date):  # Da formato legible a la tupla almacenada.
    # Se conserva la fecha capturada, sin sustituirla por la del sistema.
    return '%02d/%02d/%04d' % tuple(date)  # Conserva ceros iniciales de día y mes.


def text(value, label, limit=120):  # Valida campos de texto compartidos por las dos interfaces.
    # Los límites evitan entradas vacías o desmesuradas desde ambas interfaces.
    value = str(value).strip()  # Normaliza espacios antes de validar longitud.
    if not value or len(value) > limit:  # Exige contenido y establece un tamaño máximo.
        raise ValueError(f'{label}: escribe entre 1 y {limit} caracteres.')  # Identifica el campo que necesita corrección.
    return value  # Devuelve únicamente el texto validado.


def integer(value, label, lower=0):  # Acepta cantidades enteras dentro de los límites operativos.
    # No se truncan decimales: 1.5 y los negativos son entradas inválidas.
    if not re.fullmatch(r'\d{1,7}', str(value)) or int(value) < lower:  # Descarta fracciones, signos y cantidades excesivas.
        raise ValueError(f'{label}: usa un entero entre {lower} y 9999999.')  # Explica el intervalo permitido para este campo.
    return int(value)  # Convierte a entero solo después de validar el formato.


def price_cents(value):
    # Guarda centavos enteros para no introducir errores de redondeo monetario.
    value = str(value).strip()
    if not re.fullmatch(r'\d{1,7}(?:\.\d{1,2})?', value):
        raise ValueError('Precio: usa un importe no negativo con máximo dos decimales (ej. 250.50).')
    whole, _, fraction = value.partition('.')
    return int(whole) * 100 + int(fraction.ljust(2, '0'))


def set_price(data):
    # Permite al taller corregir el precio, también en piezas de versiones anteriores.
    code = text(data.get('code', ''), 'Código', 24).upper()
    cents = price_cents(data.get('price', ''))
    with connection() as db:
        if db.execute('UPDATE parts SET price_cents=? WHERE code=? AND active=1', (cents, code)).rowcount != 1:
            raise ValueError('No se encontró el código de refacción.')


def inventory():  # Obtiene la vista actual del inventario.
    # Se entrega una lista de diccionarios, compartida por web y consola.
    with connection() as db:  # Confirma la transacción al terminar o revierte ante un error.
        return [dict(row) for row in db.execute('SELECT * FROM parts WHERE active=1 ORDER BY name')]  # Orden alfabético para facilitar la búsqueda visual.


def history():  # Obtiene los movimientos más recientes.
    # El historial deja evidencia de quién hizo cada entrada o salida.
    with connection() as db:  # Confirma la transacción al terminar o revierte ante un error.
        return [dict(row) for row in db.execute('SELECT * FROM movements ORDER BY id DESC LIMIT 200')]  # Limita la consulta a 200 registros para la vista.


def add_part(data, date, user):  # Da de alta una pieza y deja evidencia de su creación.
    # El código normalizado permite detectar duplicados sin distinguir mayúsculas.
    code = text(data.get('code', ''), 'Código', 24).upper()  # Valida y normaliza el identificador capturado.
    if not re.fullmatch(r'[A-Z0-9-]+', code):  # Excluye símbolos no admitidos en los códigos.
        raise ValueError('Código: usa letras sin acentos, números y guiones.')  # Explica cómo corregir un identificador inválido.
    name = text(data.get('name', ''), 'Nombre')  # Exige un nombre legible de la refacción.
    category = text(data.get('category', ''), 'Categoría', 40)  # Agrupa piezas para los filtros del catálogo.
    vehicle = text(data.get('vehicle', ''), 'Aplicación')  # Registra la aplicación indicada por el personal.
    condition = data.get('condition', '')  # Recupera la condición seleccionada de la pieza.
    if condition not in STATES:  # Impide condiciones fuera del catálogo autorizado.
        raise ValueError('Selecciona una condición válida.')  # Mantiene la validación también en el servidor.
    quantity = integer(data.get('quantity', ''), 'Cantidad')  # No permite una existencia inicial negativa.
    cents = price_cents(data.get('price', ''))  # Precio unitario obligatorio en MXN.
    minimum = integer(data.get('minimum', ''), 'Stock mínimo')  # Valida el umbral que activará la alerta.
    with connection() as db:  # Confirma la transacción al terminar o revierte ante un error.
        try:
            # Inventario e historial se guardan en una misma transacción.
            db.execute('INSERT INTO parts(code,name,category,vehicle,condition,quantity,minimum,price_cents) VALUES (?,?,?,?,?,?,?,?)', (code, name, category, vehicle, condition, quantity, minimum, cents))  # Los parámetros SQL separan datos de instrucciones.
            db.execute('INSERT INTO movements(code,kind,amount,date,user,note) VALUES (?,?,?,?,?,?)', (code, 'Alta', quantity, date_text(date), user, 'Registro inicial'))
        except sqlite3.IntegrityError as error:  # Transforma el conflicto del código en un mensaje entendible.
            raise ValueError('Ya existe una refacción con ese código.') from error  # Conserva el registro previo ante códigos repetidos.
    return code  # Devuelve el identificador del alta confirmada.


def move(data, date, user):  # Procesa entradas y salidas sin inconsistencias de stock.
    # Solo se aceptan movimientos explícitos y cantidades positivas.
    code = text(data.get('code', ''), 'Código', 24).upper()  # Valida y normaliza el identificador capturado.
    kind = data.get('kind')  # Distingue recepción de piezas y despacho.
    if kind not in ('Entrada', 'Salida'):  # Evita movimientos de tipo desconocido.
        raise ValueError('Selecciona Entrada o Salida.')  # Se solicita corregir el tipo antes de modificar saldos.
    amount = integer(data.get('amount', ''), 'Cantidad', 1)  # Exige al menos una unidad por movimiento.
    note = text(data.get('note', ''), 'Motivo', 240)  # El motivo ayuda a revisar la bitácora.
    with connection() as db:  # Confirma la transacción al terminar o revierte ante un error.
        db.execute('BEGIN IMMEDIATE')  # Evita despachos simultáneos sobre el mismo saldo.
        row = db.execute('SELECT quantity FROM parts WHERE code=? AND active=1', (code,)).fetchone()  # Consulta el saldo dentro de la transacción bloqueada.
        if row is None:  # Un código inexistente no puede recibir movimientos.
            raise ValueError('No se encontró el código de refacción.')  # Permite volver a capturar un código correcto.
        quantity = row['quantity']  # Usa el saldo actual, no el enviado por el navegador.
        if kind == 'Salida':  # Aplica validaciones adicionales al despacho.
            if amount > quantity:  # Comprueba suficiencia antes de restar.
                raise ValueError('La salida supera las existencias disponibles.')  # Rechaza toda la transacción sin alterar el inventario.
            quantity -= amount  # Operador de asignación solicitado en la propuesta.
        else:
            quantity += amount  # Las entradas aumentan el inventario.
        if quantity > 9999999:  # Mantiene el mismo límite que las altas.
            raise ValueError('El inventario excede el límite permitido.')  # Solicita corregir la entrada demasiado grande.
        db.execute('UPDATE parts SET quantity=? WHERE code=?', (quantity, code))  # Actualiza exclusivamente la refacción seleccionada.
        db.execute('INSERT INTO movements(code,kind,amount,date,user,note) VALUES (?,?,?,?,?,?)', (code, kind, amount, date_text(date), user, note))
    return quantity  # Informa el saldo después de confirmar el movimiento.


def document_path(name):  # Restringe la lectura y escritura a documentos del taller.
    # No se admiten rutas ni extensiones distintas de .txt.
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}\.txt', str(name)):  # Bloquea rutas relativas, separadores y extensiones ajenas.
        raise ValueError('Nombre inválido. Ejemplo: inventario_septiembre.txt (sin espacios).')  # Da un ejemplo válido sin revelar rutas internas.
    return DOCS / name  # Compone una ruta dentro de la carpeta autorizada.


def documents():  # Expone los nombres que el usuario puede seleccionar.
    # La lista se muestra antes de pedir el nombre exacto del archivo.
    return sorted(path.name for path in DOCS.glob('*.txt') if path.is_file())  # Ordena solo archivos de texto existentes.


def read_document(name):  # Lee el contenido completo de un documento permitido.
    # FileNotFoundError se maneja en la interfaz sin terminar el programa.
    return document_path(name).read_text(encoding='utf-8')  # Los errores de lectura llegan al manejador de la interfaz.


def write_document(name, content, date, user, create=False):  # Distingue creación exclusiva de modificación de un archivo existente.
    path = document_path(name)  # Valida el nombre antes de cualquier escritura.
    content = text(content, 'Contenido', 20000)  # Impide guardar textos vacíos o excesivos.
    content = re.sub(r'\AFecha: \d{2}/\d{2}/\d{4} \| Usuario: [^\n]*\n\n', '', content, count=1)  # Renueva la cabecera anterior.
    # La cabecera registra la tupla de fecha y la persona que hizo el cambio.
    result = f'Fecha: {date_text(date)} | Usuario: {user}\n\n{content}\n'
    with LOCK:  # Serializa las modificaciones concurrentes de documentos.
        if create:  # Una creación nunca sustituye un archivo del mismo nombre.
            with path.open('x', encoding='utf-8') as file:  # No sobrescribe otro documento.
                file.write(result)  # Escribe contenido y cabecera de auditoría juntos.
        else:
            if not path.exists():  # Comprueba la existencia antes de operar sobre el archivo.
                raise FileNotFoundError('No existe el documento solicitado.')  # Modificar no debe crear silenciosamente otro archivo.
            temporary = path.with_suffix('.tmp')  # Prepara una escritura segura antes de sustituir el original.
            temporary.write_text(result, encoding='utf-8')  # Genera la versión nueva en UTF-8.
            temporary.replace(path)  # Reemplazo completo para evitar archivos parciales.


def retire_part(data, date, user):
    """Retira una pieza sin borrar su historial ni confundirla con faltantes."""
    code = text(data.get('code', ''), 'Código', 24).upper()
    note = text(data.get('note', ''), 'Motivo de baja', 240)
    if data.get('confirm') != code:
        raise ValueError('Escribe el código exacto para confirmar la baja.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT quantity FROM parts WHERE code=? AND active=1', (code,)).fetchone()
        if row is None:
            raise ValueError('La refacción no existe o ya está dada de baja.')
        db.execute('UPDATE parts SET active=0 WHERE code=?', (code,))
        db.execute('INSERT INTO movements(code,kind,amount,date,user,note) VALUES (?,?,?,?,?,?)',
                   (code, 'Baja', row['quantity'], date_text(date), user, note))
