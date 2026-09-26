# Actualización con bajas de inventario

Si ya usas el programa, lee primero ACTUALIZAR_SIN_PERDER_DATOS.md.

# El Yonkesito - Entrega final Python

Catálogo público sin cuenta. El taller entra desde **Acceso del taller** con nombre,
fecha y una contraseña propia. No requiere ChatGPT. El inventario inicia vacío y
cada pieza se registra con precio unitario en MXN.

## Primero: abrir TODO el proyecto en PyCharm

1. Descarga el ZIP y usa **Extraer todo** en Windows. No ejecutes dentro del ZIP.
2. Guarda la carpeta `yonkesito` en una ubicación permanente, por ejemplo
   `C:\Users\tu_usuario\Documents\yonkesito`.
3. En PyCharm: **File > Open**, selecciona esa carpeta completa.
4. En **Settings > Project > Python Interpreter**, elige Python 3.10 o superior
   y crea un entorno virtual `.venv` si aún no tienes intérprete.
5. Abre **Terminal** de PyCharm. Debe estar situada en la carpeta que contiene
   `app.py`, `core.py` y `requirements.txt`.
6. Ejecuta una sola vez:

```text
python -m pip install -r requirements.txt
python configurar_acceso.py
```

El segundo comando pide que escribas dos veces una contraseña de 12 a 128 caracteres.
**No verás los caracteres mientras escribes: es normal.** Hazlo en Terminal, no en
la consola de depuración. No hay contraseña predeterminada.

7. Ejecuta:

```text
python app.py
```

8. Abre **http://127.0.0.1:8000** en tu navegador y deja el programa abierto.
   También puedes ejecutar `app.py` con clic derecho > Run después de configurarlo.
9. Para administrar: pulsa **Acceso del taller**, escribe nombre o nickname,
   fecha `dd/mm/aaaa` y la contraseña que acabas de definir.
10. Para detener el servidor, pulsa Ctrl+C en Terminal o Stop en PyCharm.

Si aparece `No module named flask`, instala los requisitos con el mismo intérprete
seleccionado en PyCharm. Si aparece `No module named core`, abre la carpeta completa.
Si el directorio de trabajo contiene `Temp` o `.zip`, elimina esa configuración de
Run y crea otra apuntando a la carpeta extraída. No instales un paquete llamado core.
Si el puerto está ocupado, detén ejecuciones anteriores o configura
`YONKESITO_PORT=8001` en las variables de Run y abre esa dirección.

## Uso del taller y clientes

- Clientes: catálogo público, búsqueda, categorías, precio por pieza, condición,
  aplicación y existencias. No pueden editar ni ver documentos, mínimos o historial.
- Taller: altas individuales, editar precio, entradas, salidas, alertas, bitácora y bajas.
- Dar de baja: entra al apartado Dar de baja piezas, busca la pieza, pulsa Dar de baja,
  escribe el motivo y copia el código exacto para confirmar. La pieza queda fuera del
  inventario activo, del catálogo público y de las alertas. También se retira cualquier
  existencia que aún tenga. Se conserva el historial; no es una venta ni una salida.
- La baja no se puede deshacer desde la interfaz. El código queda reservado en el
  historial: usa otro código si necesitas registrar una refacción distinta.
- Documentos ya no aparece en la web. Las funciones de archivos siguen en consola.py
  para cubrir la rúbrica académica; los archivos existentes se conservan.
- Cambiar usuario: botón de la barra lateral. Cierra la sesión y vuelve al formulario.
- Los registros de documentos y movimientos usan la fecha capturada al ingresar.
- A los 10 minutos sin actividad, el panel pide escribir **sí** para continuar o **no**
  para volver al acceso. La sesión del servidor vence a las ocho horas, aunque haya actividad.
- Cinco intentos de clave por dirección en 15 minutos; el siguiente se bloquea hasta
  vencer el plazo. En una red compartida, varios empleados comparten ese límite.
- Cambiar contraseña: detén la aplicación, ejecuta `python configurar_acceso.py` y reinicia.
  Las sesiones anteriores dejan de tener acceso. Guarda la clave fuera del proyecto.

La contraseña es compartida por el taller, como se solicitó. El nombre capturado es
un alias de bitácora, no una identidad personal verificada; no hay permisos individuales
ni forma de revocar a un empleado sin cambiar la clave compartida.

## Demostrar la rúbrica en consola

```text
python consola.py
```

Esta versión solicita nombre y fecha, da bienvenida con concatenación, muestra una
carga de un segundo y presenta una matriz de dos columnas dentro de `while`.
Incluye leer, escribir/modificar, crear archivos, cambiar usuario, inventario y salida.
El `for` mide hasta 600 segundos para seleccionar; después exige **sí** o **no**.

La consola es una herramienta local de confianza para quien ya tiene acceso a los
archivos del proyecto; no se publica como ruta web. Usa una interfaz a la vez para
editar documentos, porque consola y web son procesos distintos.

## Entregables incluidos

- `Reporte_El_Yonkesito.pdf`: explicación de una cuartilla, dos capturas reales de
  esta versión y correspondencia con rúbrica, pruebas y limitaciones.
- `REPORTE_EDITABLE.md`: texto del reporte para completar datos del equipo.
- `ANEXO_CODIGO.html`: código Python completo, comentado e imprimible.
- Archivos `.py`: código ejecutable original, no capturas de código.
- `evidencias/`: capturas de navegador, salida de 16 pruebas y ejecución de consola.
- `datos/documentos/`: cuatro documentos TXT iniciales. No incluye base ni piezas.
- `PUBLICAR_EN_INTERNET.md` y `render.yaml`: preparación para alojamiento Python.

La parte académica está en `consola.py`; la web por sí sola no sustituye el requisito
explícito del menú en consola. Revisa el reporte y añade nombres, grupo y docente
antes de entregarlo. No se garantiza una calificación: la asigna el docente.

## Pruebas reproducibles

```text
python -m unittest -v test_proyecto.py test_web.py
```

Se usan carpetas temporales y piezas exclusivamente de prueba; no alteran tu inventario.
El aviso de diez minutos se prueba con un plazo reducido, conservando `600` segundos
en el programa normal. No se esperaron diez minutos reales en la prueba automática.

## Datos y actualización

`datos/inventario.sqlite3` se crea al iniciar. `datos/acceso.json` guarda la huella
criptográfica local de la contraseña; nunca la contraseña original. No compartas esa
carpeta ni la subas a Git. Para respaldar, detén web y consola y copia toda `datos/`
a una ubicación privada. No borres la base para actualizar.

Extrae esta versión en una carpeta nueva. No copies una base antigua si quieres
comenzar vacía. Si ya tienes datos reales, respalda y conserva el archivo de base y
los documentos: el programa conserva registros existentes y añade el campo de precio
si falta. Piezas antiguas sin importe muestran «Precio pendiente» hasta editarlo.

## Estado de publicación

Este ZIP es una aplicación Python independiente. **No modifica ni reemplaza el enlace
anterior de ChatGPT Sites.** Ejecutarla en PyCharm abre una web local; para acceso desde
cualquier lugar falta desplegarla en un alojamiento Python con HTTPS y disco persistente.
Se incluye una guía, pero en esta entrega no se contrató ni activó otro alojamiento.
