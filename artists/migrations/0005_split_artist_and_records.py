from django.db import migrations, models
import django.db.models.deletion


def copy_artist_data_to_records(apps, schema_editor):
    Artist = apps.get_model("artists", "Artist")
    ArtistRecord = apps.get_model("artists", "ArtistRecord")

    for artist in Artist.objects.all().iterator():
        ArtistRecord.objects.create(
            artista_id=artist.pk,
            es_autonomo=artist.es_autonomo,
            tipo_irpf=artist.tipo_irpf,
            fecha_alta=artist.fecha_alta,
            fecha_baja=artist.fecha_baja,
            solicitud_a1=artist.solicitud_a1,
            proceso_cancelado=artist.proceso_cancelado,
            tipo_registro=artist.tipo_registro,
            agrupacion_id=artist.agrupacion_id,
            cache_neto=artist.cache_neto,
            coste_empresa=artist.coste_empresa,
            coste_gestion=artist.coste_gestion,
            coste_seguridad_social=artist.coste_seguridad_social,
            coste_irpf=artist.coste_irpf,
            importe_entregado=artist.importe_entregado,
            estado_pago=artist.estado_pago,
            observaciones=artist.observaciones,
            creado_en=artist.creado_en,
            actualizado_en=artist.actualizado_en,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0004_artist_importe_entregado"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArtistRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("es_autonomo", models.BooleanField(default=False)),
                ("tipo_irpf", models.DecimalField(decimal_places=2, default=15.0, max_digits=5)),
                ("fecha_alta", models.DateField()),
                ("fecha_baja", models.DateField(blank=True, null=True)),
                ("solicitud_a1", models.BooleanField(default=False)),
                ("proceso_cancelado", models.BooleanField(default=False)),
                ("tipo_registro", models.CharField(choices=[("SOLO", "Solista"), ("BAND", "Banda")], default="SOLO", max_length=10)),
                ("cache_neto", models.DecimalField(decimal_places=2, max_digits=10)),
                ("coste_empresa", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("coste_gestion", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("coste_seguridad_social", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("coste_irpf", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("importe_entregado", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("estado_pago", models.CharField(choices=[("PAID", "Pagado"), ("PENDING_INVOICE", "Pendiente Factura"), ("IN_PROGRESS", "En Proceso"), ("PARTIAL", "Pago a Medias"), ("CANCELLED", "Anulado")], default="IN_PROGRESS", max_length=20)),
                ("observaciones", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("agrupacion", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registros_artistas", to="artists.grouping")),
                ("artista", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registros", to="artists.artist")),
            ],
            options={
                "verbose_name": "Registro de artista",
                "verbose_name_plural": "Registros de artistas",
                "db_table": "registros_artistas",
                "ordering": ["-fecha_alta", "-creado_en"],
            },
        ),
        migrations.RunPython(copy_artist_data_to_records, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="artist",
            name="agrupacion",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="cache_neto",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="coste_empresa",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="coste_gestion",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="coste_irpf",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="coste_seguridad_social",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="es_autonomo",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="estado_pago",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="fecha_alta",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="fecha_baja",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="importe_entregado",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="observaciones",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="proceso_cancelado",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="solicitud_a1",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="tipo_irpf",
        ),
        migrations.RemoveField(
            model_name="artist",
            name="tipo_registro",
        ),
    ]