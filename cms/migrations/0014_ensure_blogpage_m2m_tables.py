from django.db import migrations


def ensure_blogpage_m2m_tables(apps, schema_editor):
    blog_page_model = apps.get_model("cms", "BlogPage")

    existing_tables = set(schema_editor.connection.introspection.table_names())

    for field_name in ("categories", "tags"):
        field = blog_page_model._meta.get_field(field_name)
        through_model = field.remote_field.through
        table_name = through_model._meta.db_table

        if table_name in existing_tables:
            continue

        schema_editor.create_model(through_model)
        existing_tables.add(table_name)


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0013_alter_scorepage_content"),
    ]

    operations = [
        migrations.RunPython(ensure_blogpage_m2m_tables, migrations.RunPython.noop),
    ]
