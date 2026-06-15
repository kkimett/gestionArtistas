from django.db import migrations, models


def copy_gestion_to_honorarios(apps, schema_editor):
    CostPercentageSettings = apps.get_model("artists", "CostPercentageSettings")
    for settings in CostPercentageSettings.objects.all().iterator():
        settings.porcentaje_honorarios = settings.porcentaje_gestion
        settings.save(update_fields=["porcentaje_honorarios"])


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0012_alter_costpercentagesettings_at_ep_empresa_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="costpercentagesettings",
            name="porcentaje_honorarios",
            field=models.DecimalField(decimal_places=4, default=10, max_digits=7, verbose_name="Honorarios"),
        ),
        migrations.RunPython(copy_gestion_to_honorarios, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="costpercentagesettings",
            name="porcentaje_gestion",
        ),
        migrations.RemoveField(
            model_name="costpercentagesettings",
            name="porcentaje_irpf",
        ),
    ]
