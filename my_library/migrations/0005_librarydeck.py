from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("my_library", "0004_libraryitem_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryDeck",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "tags_json",
                    models.TextField(
                        help_text='JSON array of tag names, e.g. ["guitarra", "jazz"]'
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_decks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Mazo de Biblioteca",
                "verbose_name_plural": "Mazos de Biblioteca",
                "ordering": ["name"],
                "unique_together": {("user", "name")},
            },
        ),
    ]
