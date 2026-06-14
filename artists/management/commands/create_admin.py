import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea o actualiza el usuario admin de Django para acceder al sistema."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None)
        parser.add_argument("--email", default=None)
        parser.add_argument("--password", default=None)
        parser.add_argument("--first-name", default="Admin")
        parser.add_argument("--last-name", default="Sistema")

    def handle(self, *args, **options):
        username = options["username"] or os.getenv("ADMIN_USERNAME") or input("Username admin: ").strip()
        email = options["email"] or os.getenv("ADMIN_EMAIL") or input("Email admin: ").strip()
        password = options["password"] or os.getenv("ADMIN_PASSWORD") or getpass.getpass("Password admin: ").strip()
        first_name = options["first_name"].strip()
        last_name = options["last_name"].strip()

        if not username:
            raise CommandError("El username no puede estar vacío.")
        if not password:
            raise CommandError("La contraseña no puede estar vacía.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if not created:
            user.email = email or user.email
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.is_staff = True
            user.is_superuser = True

        user.set_password(password)
        user.save()

        action = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuario admin {action}: {username}"))