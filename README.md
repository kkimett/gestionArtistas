# gestionArtistas

Base Django para gestionar artistas, agrupaciones y facturas con MariaDB.

## Stack

- Django 4.2.16
- PyMySQL
- MariaDB

## Estructura

- `artists`: fichas de artistas y agrupaciones
- `billing`: facturas y resumen de pagos cobrados
- `gestion_artistas`: configuración del proyecto, URLs y settings

## Arranque

1. Copia `.env.example` a `.env` y rellena los datos de MariaDB.
2. Crea un entorno virtual con Python 3.10+.
3. Instala dependencias con `pip install -r requirements.txt`.
4. Ejecuta migraciones con `python manage.py makemigrations` y `python manage.py migrate`.
5. Crea el usuario admin con `python manage.py create_admin` o con `python manage.py create_admin --username admin --email admin@example.com --password tu-clave`.
6. Levanta el servidor con `python manage.py runserver`.

## Desarrollo local sin MySQL

- Si solo quieres ver el proyecto arrancado en tu máquina, deja `DB_ENGINE=sqlite` en `.env`.
- Si vas a conectarlo a MariaDB, cambia `DB_ENGINE=mysql` y completa los datos de conexión.
- Si trabajas desde WSL y MariaDB está en Windows, `127.0.0.1` solo funcionará si ambos corren en el mismo entorno; si no, necesitarás el host real de la máquina que expone MariaDB.

## Producción

- Usa `DEBUG=False`.
- Define siempre `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Ejecuta `python manage.py collectstatic` antes de desplegar.
- Mantén MariaDB con `STRICT_TRANS_TABLES` y una copia de seguridad regular.
- Si vas detrás de un proxy o balanceador, activa `DJANGO_SECURE_SSL_REDIRECT=true` y asegúrate de que envía `X-Forwarded-Proto`.
- En producción, crea el admin con `python manage.py create_admin` usando variables de entorno o argumentos.
- Si tu host es compartido, usa la guía de [deploy/SHARED_HOSTING.md](deploy/SHARED_HOSTING.md) y el archivo [passenger_wsgi.py](passenger_wsgi.py).
- Si tu host es un VPS, sigue [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md).

## Notas

- El formulario de login usa las vistas estándar de Django.
- El panel principal lista artistas con el desglose de costes y estado de pago.
- El resumen de pagos muestra las facturas cobradas el día actual.
- Si quieres preconfigurar credenciales, usa `ADMIN_USERNAME`, `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env`.
