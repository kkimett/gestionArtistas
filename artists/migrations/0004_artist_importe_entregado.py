from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0003_nombres_espanol"),
    ]

    operations = [
        migrations.AddField(
            model_name="artist",
            name="importe_entregado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
