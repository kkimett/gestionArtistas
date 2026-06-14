from django.core.management.base import BaseCommand
from artists.models import PriceBracket


class Command(BaseCommand):
    help = "Carga los 4 tramos de precios predefinidos"

    def handle(self, *args, **options):
        brackets_data = [
            {
                "numero_tramo": 1,
                "rango_minimo": 325,
                "rango_maximo": 400,
                "importe_base": None,
                "porcentaje_empresa": 15,
                "porcentaje_gestion": 10,
                "porcentaje_seguridad_social": 5,
                "porcentaje_irpf": 8,
            },
            {
                "numero_tramo": 2,
                "rango_minimo": 450,
                "rango_maximo": 600,
                "importe_base": 450,
                "porcentaje_empresa": 15,
                "porcentaje_gestion": 10,
                "porcentaje_seguridad_social": 5,
                "porcentaje_irpf": 8,
            },
            {
                "numero_tramo": 3,
                "rango_minimo": 600,
                "rango_maximo": 800,
                "importe_base": 600,
                "porcentaje_empresa": 15,
                "porcentaje_gestion": 10,
                "porcentaje_seguridad_social": 5,
                "porcentaje_irpf": 8,
            },
            {
                "numero_tramo": 4,
                "rango_minimo": 800,
                "rango_maximo": 999999,
                "importe_base": 800,
                "porcentaje_empresa": 15,
                "porcentaje_gestion": 10,
                "porcentaje_seguridad_social": 5,
                "porcentaje_irpf": 8,
            },
        ]

        for bracket_data in brackets_data:
            bracket, created = PriceBracket.objects.update_or_create(
                numero_tramo=bracket_data["numero_tramo"],
                defaults=bracket_data,
            )
            status = "creado" if created else "actualizado"
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Tramo {bracket.numero_tramo} ({bracket.rango_minimo}-{bracket.rango_maximo}) {status}"
                )
            )

        self.stdout.write(self.style.SUCCESS("\n¡Tramos de precios cargados exitosamente!"))
