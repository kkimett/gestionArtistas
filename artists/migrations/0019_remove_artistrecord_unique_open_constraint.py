from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0018_artistrecord_unique_open_constraint"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="artistrecord",
            name="unique_open_record_per_artist",
        ),
    ]
