"""Web Python: catálogo público y acceso del taller con contraseña propia."""
from datetime import datetime  # Proporciona fecha inicial del catálogo anónimo.
from pathlib import Path  # Resuelve archivos desde el proyecto, no desde Temp.
import hmac  # Compara tokens CSRF sin filtraciones por comparación temprana.
import os  # Separa configuración local y de alojamiento.
import sqlite3  # Identifica errores de almacenamiento para manejarlos.
from flask import Flask, request, jsonify, send_from_directory  # HTTP y servidor WSGI compatible con Gunicorn.
from werkzeug.exceptions import HTTPException  # Conserva códigos HTTP como 404 o 413.
from werkzeug.middleware.proxy_fix import ProxyFix  # Solo se activa detrás de un proxy de confianza.
import core  # Reutiliza reglas de inventario y documentos con la consola.
import seguridad  # Verifica contraseña y sesiones persistentes.


def create_app(test_config=None):  # Factoría que permite probar sin usar el inventario real.
    core.initialize()  # Empieza sin piezas y prepara cuatro documentos.
    seguridad.initialize()  # Crea tablas de sesiones y límite de intentos.
    app = Flask(__name__, static_folder=None)  # Solo se sirven recursos de la lista autorizada.
    app.config.update(MAX_CONTENT_LENGTH=100000, PASSWORD_HASH=seguridad.load_hash() if test_config is None else '', SECURE_COOKIE=os.getenv('YONKESITO_SECURE_COOKIE') == '1')  # Límite y secretos del servidor.
    if test_config:  # Solo las pruebas inyectan configuración aislada.
        app.config.update(test_config)  # No existe una ruta HTTP para cambiar esta configuración.
    if os.getenv('YONKESITO_TRUST_PROXY') == '1':  # Usar únicamente tras un proxy controlado del proveedor.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)  # Una capa de proxy, según la guía de despliegue.
    static = Path(__file__).parent / 'static'  # Funciona con directorios de ejecución distintos.

    def current_session():  # Obtiene identidad y permisos únicamente desde el servidor.
        return seguridad.get_session(request.cookies.get('session', ''), app.config['PASSWORD_HASH'])  # Una cookie inventada no permite editar.

    def public_session(value):  # Omite huellas de contraseña y datos internos.
        if not value:  # Cliente anónimo: no se pide contraseña ni cuenta de ChatGPT.
            now = datetime.now()  # Fecha de consulta, no de modificación.
            return {'name': 'Cliente', 'role': 'client', 'date': (now.day, now.month, now.year), 'csrf': ''}  # Solo lectura.
        return {key: value[key] for key in ('name', 'role', 'date', 'csrf')}  # La fecha es tupla dentro de Python.

    @app.after_request  # Añade protección tanto a pantallas como a errores.
    def protect(response):  # Centraliza encabezados.
        response.headers['Cache-Control'] = 'no-store'  # Evita datos internos en cachés compartidas.
        response.headers['X-Content-Type-Options'] = 'nosniff'  # Respeta tipos declarados.
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"  # Solo recursos propios.
        if app.config['SECURE_COOKIE']:  # HTTPS obligatorio en el alojamiento.
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'  # Recuerda el uso de HTTPS.
        return response  # No altera el resultado de negocio.

    @app.get('/')  # Catálogo directamente accesible por los clientes.
    @app.get('/taller')  # Misma interfaz con formulario de contraseña inicial.
    def page():  # Las operaciones privadas siguen comprobando la sesión en API.
        return send_from_directory(static, 'index.html')  # No acepta rutas de archivos arbitrarias.

    @app.get('/<name>')  # Sirve exclusivamente estilos, interacción y favicon.
    def asset(name):  # No se expone datos/, código Python ni configuración.
        if name not in ('style.css', 'main.js', 'favicon.svg'):  # Lista explícita de archivos públicos.
            return jsonify(error='No se encontró la página.'), 404  # No permite recorrer carpetas.
        return send_from_directory(static, name)  # MIME determinado por Flask.

    @app.get('/health')  # Comprobación del alojamiento sin datos privados.
    def health():  # Verifica que la base puede leerse.
        with core.connection() as db:  # Cierra conexión al terminar.
            db.execute('SELECT 1').fetchone()  # Consulta sin cambios.
        return jsonify(ok=True)  # No enumera piezas ni secretos.

    @app.get('/api/<action>')  # Endpoints públicos y privados comparten controles claros.
    def read(action):  # Consultas sin mutaciones.
        value = current_session()  # Verifica expiración y contraseña vigente.
        if action == 'session':  # La web restaura su vista al recargar.
            return jsonify(session=public_session(value))  # Nunca devuelve una contraseña.
        if action == 'inventory':  # Única información de negocio pública.
            items = core.inventory()  # Lista de diccionarios persistidos.
            if not value:  # Omite agotadas y mínimos internos para clientes.
                items = [{k: v for k, v in p.items() if k != 'minimum'} for p in items if p['quantity'] > 0]  # Filtro también en servidor.
            return jsonify(items=items)  # Precios en centavos enteros.
        if not value:  # Autenticación obligatoria para documentos e historial.
            return jsonify(error='Acceso exclusivo del personal del taller.'), 401  # Ocultar botones no es la protección principal.
        if action == 'history':  # Solo personal con contraseña válida.
            return jsonify(items=core.history())  # Máximo 200 en pantalla.
        return jsonify(error='No existe esa consulta.'), 404  # Mensaje controlado.

    @app.post('/api/<action>')  # Toda modificación pasa por autenticación y CSRF.
    def write(action):  # No admite métodos GET para modificar inventario.
        origin = request.headers.get('Origin')  # Rechaza formularios enviados desde otras páginas.
        if origin != request.host_url.rstrip('/') or not request.is_json:  # Acepta solo el origen propio y JSON.
            return jsonify(error='Solicitud inválida. Recarga la página.'), 403  # Compatible con HTTPS tras proxy configurado.
        data = request.get_json()  # Flask aplica también el tamaño máximo configurado.
        if not isinstance(data, dict):  # Rechaza listas o valores sin campos.
            raise ValueError('La solicitud debe ser un objeto.')  # Manejador común de errores.
        if action == 'login':  # La contraseña es la única forma de conceder el rol staff.
            ip = request.remote_addr or 'unknown'  # No confía directamente en encabezados de clientes.
            if not seguridad.reserve_attempt(ip):  # El límite es persistente y atómico.
                return jsonify(error='Demasiados intentos. Espera 15 minutos para volver a ingresar.'), 429  # No bloquea el catálogo.
            if not seguridad.verify_password(data.get('password', ''), app.config['PASSWORD_HASH']):  # Verificación del lado servidor.
                return jsonify(error='La contraseña del taller es incorrecta.'), 403  # No crea sesión.
            name = core.text(data.get('name', ''), 'Nombre', 40)  # Nombre o nickname de la rúbrica.
            date = core.date_tuple(data.get('date', ''))  # Tupla día, mes, año validada.
            seguridad.revoke(request.cookies.get('session', ''))  # Reemplaza cualquier sesión anterior de ese navegador.
            token, value = seguridad.new_session(name, date, app.config['PASSWORD_HASH'])  # Rol fijo staff.
            seguridad.clear_attempts(ip)  # Reinicia el contador después del ingreso correcto.
            response = jsonify(session=public_session(value), welcome='¡Bienvenido, ' + name + '!')  # Operador string +.
            response.set_cookie('session', token, max_age=28800, httponly=True, secure=app.config['SECURE_COOKIE'], samesite='Strict')  # JS no puede leer la cookie.
            return response  # La carga visual se presenta antes de abrir el panel.
        value = current_session()  # Nunca usa el rol recibido en JSON.
        if not value:  # Todas las demás escrituras son exclusivas del taller.
            return jsonify(error='Inicia sesión en Acceso del taller.'), 401  # Un cliente anónimo no puede editar.
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), value['csrf']):  # Impide reutilizar formularios ajenos.
            return jsonify(error='Solicitud inválida. Recarga la página.'), 403  # Conserva el inventario.
        if action == 'logout':  # Cambiar usuario cierra el acceso anterior.
            seguridad.revoke(request.cookies.get('session', ''))  # Invalida el token en SQLite.
            response = jsonify(ok=True)  # Devuelve al formulario para cambiar usuario.
            response.delete_cookie('session', secure=app.config['SECURE_COOKIE'], httponly=True, samesite='Strict')  # Limpia navegador.
            return response  # La cookie anterior ya no sirve.
        if action == 'parts':  # Alta individual con precio obligatorio.
            core.add_part(data, value['date'], value['name'])  # Comparte validaciones con consola.
        elif action == 'price':  # Actualización de precio por pieza.
            core.set_price(data)  # Centavos enteros y límite validado.
        elif action == 'move':  # Entradas y salidas con bitácora.
            core.move(data, value['date'], value['name'])  # Transacción evita existencias negativas.
        elif action == 'retire':
            core.retire_part(data, value['date'], value['name'])
        else:  # Un nombre de operación desconocido no escribe nada.
            return jsonify(error='No existe esa operación.'), 404  # Error corregible.
        return jsonify(ok=True)  # Confirma solo tras persistir los cambios.

    @app.errorhandler(Exception)  # Maneja excepciones sin exponer trazas al cliente.
    def failure(error):  # La aplicación puede continuar después de un dato inválido.
        if isinstance(error, FileNotFoundError):  # Nombre mal escrito o ausente.
            return jsonify(error='No existe ese archivo. Revisa el nombre.'), 404  # Permite intentar otro nombre.
        if isinstance(error, FileExistsError):  # Crear no sobreescribe un documento.
            return jsonify(error='Ya existe ese archivo. Elige Modificar.'), 409  # Conserva el anterior.
        if isinstance(error, ValueError):  # Fechas, cantidades y nombres inválidos.
            return jsonify(error=str(error)), 400  # Muestra el campo a corregir.
        if isinstance(error, HTTPException):  # JSON inválido, tamaño excesivo o ruta incorrecta.
            return jsonify(error='Solicitud no válida.'), error.code  # Conserva el código HTTP apropiado.
        app.logger.error('Fallo interno', exc_info=error)  # Depuración del lado del servidor.
        return jsonify(error='No se pudo completar la operación. Revisa el servidor.'), 503  # No entrega rutas ni SQL.
    return app  # WSGI para local, pruebas o Gunicorn.


if __name__ == '__main__':  # Ejecutar desde PyCharm inicia la aplicación local.
    try:  # Explica la configuración pendiente en vez de mostrar una traza.
        application = create_app()  # La contraseña debe configurarse previamente.
        port = int(os.getenv('YONKESITO_PORT', '8000'))  # Permite resolver un puerto ocupado.
        print(f'Abre http://127.0.0.1:{port} en tu navegador.')  # Dirección local explícita.
        application.run(host='127.0.0.1', port=port, debug=False)  # Internet usa Gunicorn, no este servidor local.
    except (RuntimeError, ValueError, OSError) as error:  # Errores habituales de configuración.
        print('No se pudo iniciar:', error)  # Instrucción para corregir antes de reintentar.
