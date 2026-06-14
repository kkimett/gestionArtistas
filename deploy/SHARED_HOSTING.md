# Despliegue en hosting compartido

Este proyecto está preparado para un hosting compartido con Python, normalmente mediante cPanel, CloudLinux o Passenger.

## Lo que necesitas

- Un hosting que permita aplicaciones Python/WSGI.
- Acceso a un entorno virtual o al instalador de paquetes del panel.
- Una base de datos MariaDB.
- Un dominio o subdominio asociado a la aplicación.

## Archivos clave

- `passenger_wsgi.py`: punto de entrada WSGI para hosts tipo Passenger/cPanel.
- `gestion_artistas/wsgi.py`: configuración estándar de Django.
- `deploy/`: documentación y ejemplos de despliegue.

## Pasos recomendados

1. Sube el proyecto al directorio de la aplicación dentro del hosting.
2. Crea la base de datos MariaDB y anota nombre, usuario, contraseña y host.
3. Crea el entorno virtual desde el panel del hosting o por SSH si está disponible.
4. Instala dependencias con `pip install -r requirements.txt`.
5. Copia `.env.example` a `.env` y completa:
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS`
   - `DJANGO_CSRF_TRUSTED_ORIGINS`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
6. Ejecuta migraciones con `python manage.py migrate`.
7. Crea el superusuario con `python manage.py create_admin`.
8. Ejecuta `python manage.py collectstatic --noinput`.
9. Configura el panel del hosting para que use `passenger_wsgi.py` como entry point si te lo pide.

## Notas importantes

- En hosting compartido normalmente no necesitas Gunicorn ni systemd.
- Si el proveedor sirve estáticos desde el mismo directorio, puedes seguir usando WhiteNoise sin tocar nada.
- Si el panel no permite `collectstatic` automático, ejecútalo manualmente tras cada despliegue.
- Si el proveedor usa subdominios o una ruta no raíz, ajusta `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`.
