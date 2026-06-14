# Despliegue sin Docker

Este proyecto está preparado para un VPS o servidor clásico con Python, MariaDB, Gunicorn y Nginx.

## Requisitos

- Python 3.10+
- MariaDB 10.5+ o compatible
- Nginx
- Un entorno virtual en `.venv`
- No necesitas `mysqlclient`; el proyecto usa `PyMySQL`

## Pasos

1. Copia `.env.example` a `.env` y completa `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y los datos de MariaDB.
2. Instala dependencias con `pip install -r requirements.txt`.
3. Ejecuta `python manage.py migrate`.
4. Crea el superusuario con `python manage.py create_admin`.
5. Recoge estáticos con `python manage.py collectstatic --noinput`.
6. Inicia Gunicorn con `gunicorn gestion_artistas.wsgi:application --config deploy/gunicorn.conf.py`.
7. Configura Nginx usando `deploy/nginx.conf.example` para servir `/static/` y `/media/` y reenviar al puerto 8000.
8. Si lo prefieres como servicio, instala `deploy/gestionartistas.service.example` como unidad systemd.

## Variables importantes

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
