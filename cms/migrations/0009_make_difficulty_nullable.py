# Generated manually to fix IntegrityError
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0008_alter_scorepage_content"),
    ]

    operations = [
        # Primero: hacer el campo nullable si existe
        migrations.RunSQL(
            sql="ALTER TABLE cms_scorepage ALTER COLUMN difficulty_level DROP NOT NULL;",
            reverse_sql="ALTER TABLE cms_scorepage ALTER COLUMN difficulty_level SET NOT NULL;",
            state_operations=[],  # No cambia el estado de Django
        ),
        # Segundo: eliminar el campo si existe
        migrations.RunSQL(
            sql="ALTER TABLE cms_scorepage DROP COLUMN IF EXISTS difficulty_level;",
            reverse_sql="",  # No reversible
            state_operations=[],
        ),
        # Tercero: eliminar el campo rating si existe
        migrations.RunSQL(
            sql="ALTER TABLE cms_scorepage DROP COLUMN IF EXISTS rating;",
            reverse_sql="",
            state_operations=[],
        ),
    ]
