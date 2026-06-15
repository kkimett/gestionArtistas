from django.db import migrations


def ensure_sectional_percentage_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "configuracion_porcentajes"

    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if table_name not in tables:
            return

        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

        quote_name = connection.ops.quote_name

        def add_decimal_column(column_name, default_value):
            if column_name in columns:
                return

            if connection.vendor == "mysql":
                sql_type = "DECIMAL(5,2)"
            elif connection.vendor == "sqlite":
                sql_type = "decimal"
            else:
                sql_type = "NUMERIC(5,2)"

            cursor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                f"ADD COLUMN {quote_name(column_name)} {sql_type} NOT NULL DEFAULT {default_value}"
            )
            columns.add(column_name)

        add_decimal_column("contingencias_comunes_empresa", 15)
        add_decimal_column("contingencias_comunes_trabajador", 5)
        add_decimal_column("mei_empresa", 0)
        add_decimal_column("mei_trabajador", 0)
        add_decimal_column("desempleo_empresa", 0)
        add_decimal_column("desempleo_trabajador", 0)
        add_decimal_column("formacion_empresa", 0)
        add_decimal_column("formacion_trabajador", 0)
        add_decimal_column("at_ep_empresa", 0)
        add_decimal_column("fogasa_empresa", 0)

        if "porcentaje_empresa" in columns:
            cursor.execute(
                f"UPDATE {quote_name(table_name)} "
                f"SET {quote_name('contingencias_comunes_empresa')} = {quote_name('porcentaje_empresa')}"
            )

        if "porcentaje_seguridad_social" in columns:
            cursor.execute(
                f"UPDATE {quote_name(table_name)} "
                f"SET {quote_name('contingencias_comunes_trabajador')} = {quote_name('porcentaje_seguridad_social')}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("artists", "0010_costpercentagesettings_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_sectional_percentage_columns, migrations.RunPython.noop),
    ]