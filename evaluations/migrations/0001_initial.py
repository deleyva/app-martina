# Generated by Django 5.0.11 on 2025-03-17 15:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='RubricItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('order', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('group', models.CharField(max_length=50)),
                ('pending_evaluation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pending_students', to='evaluations.evaluationitem')),
            ],
        ),
        migrations.CreateModel(
            name='Evaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.DecimalField(decimal_places=2, max_digits=4)),
                ('date_evaluated', models.DateTimeField(auto_now_add=True)),
                ('evaluation_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='evaluations.evaluationitem')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='evaluations.student')),
            ],
            options={
                'ordering': ['-date_evaluated'],
                'unique_together': {('student', 'evaluation_item')},
            },
        ),
    ]
