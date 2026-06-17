from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0017_groupingrecordbatch"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="artistrecord",
            constraint=models.UniqueConstraint(
                condition=models.Q(fecha_baja__isnull=True),
                fields=("artista",),
                name="unique_open_record_per_artist",
            ),
        ),
    ]
