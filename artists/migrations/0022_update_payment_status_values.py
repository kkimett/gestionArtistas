from django.db import migrations, models


def migrate_payment_status_values(apps, schema_editor):
    artist_record = apps.get_model("artists", "ArtistRecord")
    grouping_batch = apps.get_model("artists", "GroupingRecordBatch")

    status_map = {
        "PAID": "ABONADO",
        "PENDING_INVOICE": "PENDIENTE",
        "IN_PROGRESS": "PENDIENTE",
        "PARTIAL": "A_MEDIAS",
        "CANCELLED": "PENDIENTE",
    }

    for old_value, new_value in status_map.items():
        artist_record.objects.filter(estado_pago=old_value).update(estado_pago=new_value)
        grouping_batch.objects.filter(estado_pago=old_value).update(estado_pago=new_value)


def reverse_payment_status_values(apps, schema_editor):
    artist_record = apps.get_model("artists", "ArtistRecord")
    grouping_batch = apps.get_model("artists", "GroupingRecordBatch")

    reverse_map = {
        "ABONADO": "PAID",
        "PENDIENTE": "IN_PROGRESS",
        "A_MEDIAS": "PARTIAL",
        "ADELANTO": "CANCELLED",
    }

    for old_value, new_value in reverse_map.items():
        artist_record.objects.filter(estado_pago=old_value).update(estado_pago=new_value)
        grouping_batch.objects.filter(estado_pago=old_value).update(estado_pago=new_value)


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0021_artistrecord_estado_seguridad_social_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_payment_status_values, reverse_payment_status_values),
        migrations.AlterField(
            model_name="artistrecord",
            name="estado_pago",
            field=models.CharField(
                choices=[
                    ("ABONADO", "Abonado"),
                    ("PENDIENTE", "Pendiente"),
                    ("A_MEDIAS", "A medias"),
                    ("ADELANTO", "Adelanto"),
                ],
                default="PENDIENTE",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="groupingrecordbatch",
            name="estado_pago",
            field=models.CharField(
                choices=[
                    ("ABONADO", "Abonado"),
                    ("PENDIENTE", "Pendiente"),
                    ("A_MEDIAS", "A medias"),
                    ("ADELANTO", "Adelanto"),
                ],
                default="PENDIENTE",
                max_length=20,
            ),
        ),
    ]
