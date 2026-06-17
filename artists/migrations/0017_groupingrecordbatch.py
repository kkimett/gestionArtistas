from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0016_artistrecord_destino_a1"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupingRecordBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lineas", models.JSONField(default=list)),
                ("fecha_alta", models.DateField()),
                ("fecha_baja", models.DateField(blank=True, null=True)),
                ("proceso_cancelado", models.BooleanField(default=False)),
                (
                    "estado_pago",
                    models.CharField(
                        choices=[
                            ("PAID", "Pagado"),
                            ("PENDING_INVOICE", "Pendiente pago"),
                            ("IN_PROGRESS", "En Proceso"),
                            ("PARTIAL", "Pago a Medias"),
                            ("CANCELLED", "Anulado"),
                        ],
                        default="IN_PROGRESS",
                        max_length=20,
                    ),
                ),
                ("observaciones", models.TextField(blank=True)),
                (
                    "estado",
                    models.CharField(
                        choices=[("STANDBY", "Stand By"), ("PROCESSED", "Procesado")],
                        default="STANDBY",
                        max_length=20,
                    ),
                ),
                ("generado_en", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "agrupacion",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lotes_registros", to="artists.grouping"),
                ),
            ],
            options={
                "verbose_name": "Lote de registros por agrupacion",
                "verbose_name_plural": "Lotes de registros por agrupacion",
                "db_table": "lotes_registros_agrupaciones",
                "ordering": ["-creado_en"],
            },
        ),
    ]
