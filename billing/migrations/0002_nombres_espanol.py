from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0003_nombres_espanol"),
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="invoice",
            table="facturas",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="artist",
            new_name="artista",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="reference",
            new_name="referencia",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="invoice_date",
            new_name="fecha_factura",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="due_date",
            new_name="fecha_vencimiento",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="paid_at",
            new_name="fecha_cobro",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="amount",
            new_name="importe",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="status",
            new_name="estado",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="notes",
            new_name="notas",
        ),
        migrations.RenameField(
            model_name="invoice",
            old_name="created_at",
            new_name="creado_en",
        ),
        migrations.AlterField(
            model_name="invoice",
            name="artista",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="facturas", to="artists.artist"),
        ),
        migrations.AlterModelOptions(
            name="invoice",
            options={"ordering": ["-fecha_factura", "referencia"], "verbose_name": "Factura", "verbose_name_plural": "Facturas"},
        ),
    ]
