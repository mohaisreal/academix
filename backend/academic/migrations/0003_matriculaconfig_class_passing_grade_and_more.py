# Generado por Django 5.2.12 el 2026-03-31 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0002_add_total_spots_and_deadline'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatriculaConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempt_number', models.PositiveSmallIntegerField(help_text='Número de matrícula. El valor 4 representa "4ª o más".', unique=True)),
                ('label', models.CharField(max_length=50)),
                ('price_per_credit', models.DecimalField(decimal_places=2, max_digits=8)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['attempt_number'],
            },
        ),
        migrations.AddField(
            model_name='class',
            name='passing_grade',
            field=models.DecimalField(decimal_places=2, default=5.0, help_text='Nota mínima para superar la asignatura (0.00–10.00)', max_digits=4),
        ),
        migrations.AddField(
            model_name='subject',
            name='subject_type',
            field=models.CharField(choices=[('basica', 'Formación Básica'), ('obligatoria', 'Obligatoria'), ('optativa', 'Optativa'), ('practicas', 'Prácticas Externas'), ('tfg', 'TFG / TFM')], default='obligatoria', max_length=12),
        ),
    ]
