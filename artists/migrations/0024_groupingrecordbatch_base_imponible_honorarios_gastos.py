from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0023_merge_0022_payment_status_and_facturacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupingrecordbatch",
            name="base_imponible",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="groupingrecordbatch",
            name="gastos",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="groupingrecordbatch",
            name="honorarios",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
