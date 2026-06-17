from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0019_remove_artistrecord_unique_open_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="artistrecord",
            name="lote_agrupacion",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registros_creados", to="artists.groupingrecordbatch"),
        ),
    ]
