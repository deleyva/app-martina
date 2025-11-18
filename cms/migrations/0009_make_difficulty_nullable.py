# Generated manually to fix IntegrityError
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0008_alter_scorepage_content"),
    ]

    operations = [
        # Hacer nullable SOLO si la columna existe
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'cms_scorepage'
                        AND column_name = 'difficulty_level'
                    ) THEN
                        ALTER TABLE cms_scorepage ALTER COLUMN difficulty_level DROP NOT NULL;
                    END IF;
                END $$;
            """,
            reverse_sql="",
            state_operations=[],
        ),
        # Eliminar el campo si existe
        migrations.RunSQL(
            sql="ALTER TABLE cms_scorepage DROP COLUMN IF EXISTS difficulty_level;",
            reverse_sql="",
            state_operations=[],
        ),
        # Eliminar el campo rating si existe
        migrations.RunSQL(
            sql="ALTER TABLE cms_scorepage DROP COLUMN IF EXISTS rating;",
            reverse_sql="",
            state_operations=[],
        ),
    ]
