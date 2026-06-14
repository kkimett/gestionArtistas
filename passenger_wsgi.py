import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_artistas.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
