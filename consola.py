"""Menú académico: while, for, matriz, tuplas y archivos con espera real."""
import queue  # Comunica el lector de teclado con el temporizador.
import sys  # Permite terminar limpiamente cuando se cierra la entrada estándar.
import threading  # Evita que input() bloquee la medición del tiempo.
import time  # Usa un reloj monotónico para medir intervalos.
import core  # Comparte inventario y validaciones con la versión web.

# Un único lector permanece activo; no se acumulan hilos tras cada espera.
INPUT = queue.Queue()
EOF = object()  # Distingue fin de entrada de una línea vacía válida.


def keyboard_reader():  # Un lector único evita hilos acumulados durante la espera.
    # Funciona en terminales de Windows, macOS y Linux, incluida PyCharm.
    while True:
        try:
            INPUT.put(input())  # El hilo principal recoge después esta respuesta.
        except EOFError:
            INPUT.put(EOF)  # El programa saldrá sin un bucle infinito de errores.
            return


def ask(prompt):  # Recoge una entrada del lector de teclado compartido.
    print(prompt, end='', flush=True)  # Muestra el texto antes de esperar la entrada.
    answer = INPUT.get()  # Reutiliza el único lector, incluso después del temporizador.
    if answer is EOF:
        raise EOFError  # El bloque principal convierte el fin de entrada en salida normal.
    return answer.strip()  # Descarta espacios accidentales al inicio y al final.


def loading(seconds=1):  # Mantiene visible el aviso durante una espera acotada.
    # La espera queda limitada a cinco segundos, incluso si se cambia el parámetro.
    print('Cargando el programa…', flush=True)
    time.sleep(min(max(seconds, 0), 5))  # En la ejecución normal dura un segundo.


def timed_option(seconds=600):  # Mide la selección; el valor normal es diez minutos.
    print('Selecciona una opción: ', end='', flush=True)  # Inicia la medición del menú.
    started = time.monotonic()  # El reloj no cambia si se ajusta la hora del sistema.
    for second in range(seconds):  # Requisito: ciclo for para medir hasta diez minutos.
        remaining = started + second + 1 - time.monotonic()  # Calcula el plazo del segundo actual.
        try:
            result = INPUT.get(timeout=max(remaining, 0))  # Espera sin consumir CPU continuamente.
            if result is EOF:
                raise EOFError  # Salir si se cierra la consola.
            print(f'Tiempo para seleccionar: {time.monotonic()-started:.1f} segundos.')
            return result.strip()  # Devuelve la opción sin esperar los segundos restantes.
        except queue.Empty:
            continue  # Un segundo sin entrada no termina todavía la espera.
    print('\nHan pasado 10 minutos sin seleccionar una opción.')  # El plazo normal es 600 s.
    while True:
        answer = ask('¿Deseas continuar? Escribe sí o no: ').lower()  # Respuesta explícita solicitada.
        if answer in ('sí', 'si'):
            return 'continue'  # Mantiene usuario y vuelve a presentar el menú.
        if answer == 'no':
            return 'change'  # Regresa a la captura de usuario.
        print('Respuesta inválida: escribe sí o no.')  # No se acepta una opción ambigua.


def login():  # Solicita los datos académicos antes de presentar el menú.
    while True:
        try:
            name = core.text(ask('\nNombre o nickname: '), 'Nombre', 40)  # Rechaza nombre vacío.
            date = core.date_tuple(ask('Fecha (dd/mm/aaaa): '))  # Almacena día, mes y año en tupla.
            print('¡Bienvenido, ' + name + '!')  # Concatenación mediante operadores de string.
            loading()  # Aviso de carga visible durante un segundo.
            return name, date  # El menú conserva la fecha capturada.
        except ValueError as error:
            print('Dato inválido:', error)  # Un error vuelve a solicitar los datos.


def show_inventory():  # Recorre las piezas y muestra precio y alerta de mínimo.
    print('\nCÓDIGO        PIEZA                              STOCK   MÍNIMO   ALERTA / PRECIO MXN')
    for part in core.inventory():  # Lista de diccionarios retornada por el modelo.
        low = part['quantity'] <= part['minimum']  # Incluye existencias iguales al mínimo.
        print(f"{part['code']:<13} {part['name']:<34} {part['quantity']:<7} {part['minimum']:<8} {'REABASTECER' if low else 'OK'} | {('Pendiente' if part['price_cents'] is None else format(part['price_cents']/100, '.2f'))}")


def main():  # Coordina la matriz y repite el menú hasta salir.
    core.initialize()  # Garantiza cuatro archivos previos antes de mostrarlos.
    threading.Thread(target=keyboard_reader, daemon=True).start()  # Un solo lector de teclado.
    name, date = login()  # Solicita datos antes de permitir operaciones.
    options = [  # Matriz con dos columnas: opción y descripción.
        ['1', 'Leer un archivo'],
        ['2', 'Escribir / modificar un archivo'],
        ['3', 'Crear un archivo'],
        ['4', 'Cambiar usuario'],
        ['5', 'Consultar inventario y alertas'],
        ['6', 'Registrar refacción'],
        ['7', 'Registrar entrada'],
        ['8', 'Registrar salida'],
        ['0', 'Salir'],
    ]
    while True:  # El menú se repite hasta que la persona elija salir.
        print('\nEL YONKESITO | ' + name + ' | ' + core.date_text(date))
        print(f"{'OPCIÓN':<8} | ACCIÓN")  # Encabezados visibles del menú tabular.
        print('-' * 49)  # Operador string para separar el encabezado.
        for key, label in options:
            print(f'{key:<8} | {label}')  # Presenta cada fila de la matriz.
        try:
            choice = timed_option()  # Espera hasta 600 segundos usando for.
            if choice == '0':
                print('Hasta pronto, ' + name + '.')  # Mensaje de despedida personalizado.
                break  # Única salida elegida del menú principal.
            if choice in ('4', 'change'):
                name, date = login()  # Cambiar usuario también permite capturar otra fecha.
            elif choice == 'continue':
                continue  # Repite la matriz con el mismo usuario.
            elif choice in ('1', '2', '3'):
                print('Archivos disponibles:', core.documents())  # Lista antes de solicitar el nombre.
                filename = ask('Nombre exacto del archivo (con .txt): ')  # Permite detectar errores de escritura.
                if choice == '1':
                    print(core.read_document(filename))  # Lectura real de un archivo de texto.
                else:
                    if choice == '2':
                        print('Contenido actual:\n' + core.read_document(filename))  # Valida que exista.
                    content = ask('Escribe el contenido nuevo (una línea): ')  # Sustituye el texto anterior.
                    core.write_document(filename, content, date, name, create=choice == '3')
                    print('Archivo guardado con fecha ' + core.date_text(date))  # Evidencia el uso de la tupla.
            elif choice == '5':
                show_inventory()  # Comparte el mismo inventario persistente que la web.
            elif choice == '6':
                fields = [('code', 'Código'), ('name', 'Nombre'), ('category', 'Categoría'), ('vehicle', 'Aplicación'), ('condition', 'Condición: Usada, Nueva o Reacondicionada'), ('quantity', 'Existencias'), ('minimum', 'Stock mínimo'), ('price', 'Precio unitario en MXN')]
                data = {key: ask(label + ': ') for key, label in fields}  # Captura los campos en un diccionario.
                core.add_part(data, date, name)  # Valida duplicados y cantidades antes de guardar.
                print('Refacción registrada.')  # Confirma una transacción completada.
            elif choice in ('7', '8'):
                data = {'code': ask('Código: '), 'amount': ask('Cantidad: '), 'note': ask('Motivo: '), 'kind': 'Entrada' if choice == '7' else 'Salida'}
                print('Existencias actualizadas:', core.move(data, date, name))  # Nunca permite stock negativo.
            else:
                print('Opción inválida. Elige un número de la matriz.')  # El menú continúa disponible.
        except (ValueError, OSError, UnicodeError) as error:
            print('No se pudo completar la operación:', error)  # Maneja nombres erróneos y archivos inexistentes.


if __name__ == '__main__':
    try:
        main()  # Ejecutar este archivo abre la versión académica en consola.
    except (EOFError, KeyboardInterrupt):
        print('\nPrograma finalizado.')  # Ctrl+C no muestra un error técnico al usuario.
        sys.exit(0)  # Terminación normal, no un fallo de ejecución.
