from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0020_remove_classsessionitem_session_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluationitem",
            name="term",
            field=models.CharField(
                blank=True,
                choices=[
                    ("primera", "Primera evaluación"),
                    ("segunda", "Segunda evaluación"),
                    ("tercera", "Tercera evaluación"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
