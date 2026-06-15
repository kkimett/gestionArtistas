from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0005_split_artist_and_records"),
    ]

    operations = [
        migrations.AddField(
            model_name="grouping",
            name="artistas",
            field=models.ManyToManyField(blank=True, related_name="agrupaciones", to="artists.artist"),
        ),
    ]
