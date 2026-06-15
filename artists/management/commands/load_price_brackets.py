from django.core.management.base import BaseCommand
from artists.models import CostPercentageSettings, PriceBracket


class Command(BaseCommand):
    help = "Carga los 4 tramos de precios predefinidos"

    def handle(self, *args, **options):
        brackets_data = [
            {
                "numero_tramo": 1,
                "rango_minimo": 325,
                "rango_maximo": 400,
                "importe_base": None,
            },
            {
                "numero_tramo": 2,
                "rango_minimo": 450,
                "rango_maximo": 600,
                "importe_base": 450,
            },
            {
                "numero_tramo": 3,
                "rango_minimo": 600,
                "rango_maximo": 800,
                "importe_base": 600,
            },
            {
                "numero_tramo": 4,
                "rango_minimo": 800,
                "rango_maximo": 999999,
                "importe_base": 800,
            },
        ]

        CostPercentageSettings.objects.update_or_create(
            pk=1,
            defaults={
                "contingencias_comunes_empresa": 15,
                "contingencias_comunes_trabajador": 5,
                "mei_empresa": 0,
                "mei_trabajador": 0,
                "desempleo_empresa": 0,
                "desempleo_trabajador": 0,
                "formacion_empresa": 0,
                "formacion_trabajador": 0,
                "at_ep_empresa": 0,
                "fogasa_empresa": 0,
                "porcentaje_honorarios": 10,
            },
        )

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
