# Generado por Django 5.2.12 el 2026-03-31 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='weight',
            field=models.DecimalField(decimal_places=2, default=100, help_text='Peso porcentual en la nota final (0–100). La suma de todos los pesos de una clase debe ser 100.', max_digits=5),
        ),
    ]
