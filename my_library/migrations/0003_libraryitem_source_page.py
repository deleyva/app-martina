import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0001_initial"),
        ("my_library", "0002_alter_libraryitem_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="libraryitem",
            name="source_page",
            field=models.ForeignKey(
                blank=True,
                help_text="Página desde la que se añadió este elemento",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="library_items_from",
                to="wagtailcore.page",
                verbose_name="Página de origen",
            ),
        ),
    ]
