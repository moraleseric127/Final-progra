"""Ejecutar en la terminal de PyCharm para crear o cambiar la clave del taller."""
import getpass  # Oculta la contraseña durante la captura.
import json  # Guarda únicamente su derivación criptográfica.
import os  # Restringe permisos locales cuando el sistema lo permite.
import sys  # Permite generar la configuración del alojamiento.
import core  # Usa la misma carpeta de datos que el servidor.
from seguridad import hash_password  # Comparte la política de longitud y algoritmo.


def main():  # No existe una contraseña predeterminada en esta entrega.
    print('CONFIGURACIÓN DEL ACCESO DEL TALLER')  # Diferencia configuración de inicio de sesión.
    password = getpass.getpass('Nueva contraseña (12 a 128 caracteres): ')  # No se imprime ni guarda en claro.
    confirm = getpass.getpass('Repite la contraseña: ')  # Evita configurar una clave con errores de escritura.
    if password != confirm:  # No altera la clave anterior ante un error.
        raise ValueError('Las contraseñas no coinciden. Ejecuta el programa de nuevo.')  # Explicación directa.
    encoded = hash_password(password)  # Aplica la validación antes de escribir.
    if '--alojamiento' in sys.argv:  # Genera un valor que se puede copiar al panel del proveedor.
        print('Copia SOLO la siguiente línea en YONKESITO_PASSWORD_HASH del alojamiento:')  # La huella también debe mantenerse privada.
        print(encoded)  # Salida solicitada expresamente con --alojamiento.
        return  # No cambia el acceso local en este modo.
    core.ROOT.mkdir(parents=True, exist_ok=True)  # Crea carpeta local si aún no existe.
    path = core.ROOT / 'acceso.json'  # Nunca debe subirse al repositorio ni incluirse en la entrega.
    temporary = path.with_suffix('.tmp')  # Escritura completa antes de reemplazar.
    temporary.write_text(json.dumps({'password_hash': encoded}), encoding='utf-8')  # Solo la huella queda persistida.
    os.chmod(temporary, 0o600)  # Solo el propietario en sistemas POSIX; usar permisos NTFS en Windows.
    temporary.replace(path)  # Confirma el cambio al terminar la escritura.
    print('Acceso configurado. Reinicia app.py si estaba abierto.')  # El reinicio aplica la clave nueva e invalida sesiones anteriores.


if __name__ == '__main__':  # Importar el módulo no solicita contraseñas.
    try:  # Los errores no imprimen datos sensibles.
        main()  # Ejecuta la configuración interactiva.
    except (ValueError, OSError, KeyboardInterrupt, EOFError) as error:  # Maneja cancelaciones o fallos de archivo.
        print('No se completó la configuración:', error)  # Mantiene instrucciones legibles.
        sys.exit(1)  # Permite detectar un fallo desde una terminal.
