from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0015_alter_costpercentagesettings_at_ep_empresa_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="artistrecord",
            name="destino_a1",
            field=models.CharField(blank=True, max_length=255, verbose_name="Destino A1"),
        ),
    ]
