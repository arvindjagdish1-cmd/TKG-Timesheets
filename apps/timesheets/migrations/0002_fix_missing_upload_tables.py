from django.db import migrations


def create_missing_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    model_names = [
        "ClientMapping",
        "TimesheetUpload",
    ]

    for model_name in model_names:
        model = apps.get_model("timesheets", model_name)
        if model._meta.db_table not in existing_tables:
            schema_editor.create_model(model)


class Migration(migrations.Migration):
    dependencies = [
        ("timesheets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_tables, migrations.RunPython.noop),
    ]
