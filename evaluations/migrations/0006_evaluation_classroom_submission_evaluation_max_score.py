# Generated by Django 5.0.11 on 2025-04-13 21:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0005_remove_student_first_name_remove_student_last_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='classroom_submission',
            field=models.BooleanField(default=False, verbose_name='Entrega por classroom'),
        ),
        migrations.AddField(
            model_name='evaluation',
            name='max_score',
            field=models.DecimalField(decimal_places=1, default=10.0, max_digits=3, verbose_name='Nota máxima'),
        ),
    ]
