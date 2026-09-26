# Publicar la versión Python con contraseña propia

## Estado actual

El código está preparado y probado localmente. Aún NO tiene una URL pública nueva.
El sitio anterior conserva su acceso por ChatGPT y sus datos separados. Este paquete
no sincroniza inventarios con ese sitio ni con otra instalación de PyCharm.

## Opción preparada: Render con almacenamiento persistente

Requiere que el titular cree una cuenta, conecte un repositorio y elija un servicio con
disco persistente. El archivo `render.yaml` selecciona un plan `starter` con disco de 1 GB;
esto puede generar cargos. Revisa la tarifa vigente en el proveedor antes de confirmar.
No se contrató ningún servicio en esta entrega.

1. Sube el contenido de la carpeta `yonkesito` a un repositorio de tu cuenta, con
   `render.yaml` en la raíz. Excluye datos reales, contraseñas, `.venv`, `__pycache__`,
   `.env` y `datos/`; `.gitignore` ya lo indica.
2. En tu terminal local ejecuta:

```text
python configurar_acceso.py --alojamiento
```

3. Elige la contraseña del taller y copia la huella generada (una sola línea).
   Trátala como configuración privada. No la pegues en el código ni en el chat.
4. En Render crea un Blueprint desde el repositorio. Antes de crear recursos,
   confirma el costo del plan y del disco. Configura `YONKESITO_PASSWORD_HASH` con
   la huella anterior en el campo privado solicitado por el panel.
5. La plantilla instala requisitos y ejecuta:

```text
gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT 'app:create_app()'
```

6. La plantilla fija `YONKESITO_DATA=/var/data/yonkesito` dentro del disco montado,
   activa cookies HTTPS y configura una capa de proxy. Estos valores deben mantenerse
   acordes con la red del alojamiento. No uses `TRUST_PROXY=1` en un servidor directo.
7. Cuando el proveedor confirme el despliegue, abre su URL HTTPS. En una ventana privada
   comprueba que se ve el catálogo sin iniciar sesión. En «Acceso del taller» entra con
   la contraseña elegida, registra una pieza real con precio y revisa la consulta pública.
8. Reinicia el servicio desde el proveedor y verifica que la pieza continúa guardada.
   Prueba también cerrar sesión y comprobar que ya no puedes editar.
9. Comparte la nueva URL con clientes. No compartas la contraseña ni el acceso al proveedor.

El directorio normal del servicio es efímero: sin disco persistente podrían perderse
inventario, sesiones y documentos al reiniciar o desplegar. Esta versión usa SQLite y
archivos locales, por lo que se configura UNA instancia y UN proceso Gunicorn con hilos.
Para varios procesos/instancias haría falta adaptar el almacenamiento y el bloqueo de archivos.

## Cambiar la contraseña publicada

Genera otra huella con el mismo comando, cambia `YONKESITO_PASSWORD_HASH` en el panel y
reinicia o vuelve a desplegar el servicio. Las sesiones firmadas con la revisión anterior
quedan invalidadas. Informa la nueva clave al personal por un medio privado.

## Respaldo y mantenimiento

Para un respaldo consistente, detén escrituras y copia `/var/data/yonkesito` completo a
un destino privado o utiliza las funciones de respaldo del proveedor. Prueba restaurarlo
antes de depender del sistema para operaciones reales. El reporte refleja pruebas locales;
no equivale a una auditoría ni a una prueba del servicio publicado.

## Documentación oficial consultada el 24/09/2026

- Flask, despliegue: https://flask.palletsprojects.com/en/stable/deploying/
- Flask, Gunicorn: https://flask.palletsprojects.com/en/stable/deploying/gunicorn/
- Render, discos persistentes: https://render.com/docs/disks
- Render, referencia de Blueprint: https://render.com/docs/blueprint-spec
