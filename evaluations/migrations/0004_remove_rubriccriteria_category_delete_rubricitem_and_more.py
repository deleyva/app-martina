# Generated by Django 5.0.11 on 2025-04-09 08:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0003_rubriccategory_rubriccriteria_rubricscore'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='rubriccriteria',
            name='category',
        ),
        migrations.DeleteModel(
            name='RubricItem',
        ),
        migrations.AlterField(
            model_name='rubriccategory',
            name='max_points',
            field=models.DecimalField(decimal_places=1, default=2.0, max_digits=3),
        ),
        migrations.AlterField(
            model_name='rubricscore',
            name='points',
            field=models.DecimalField(decimal_places=1, max_digits=3),
        ),
        migrations.DeleteModel(
            name='RubricCriteria',
        ),
    ]
