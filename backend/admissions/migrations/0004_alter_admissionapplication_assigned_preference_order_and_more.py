# Generado por Django 5.2.12 el 2026-03-31 16:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0003_preinscripcion_redesign'),
    ]

    operations = [
        migrations.AlterField(
            model_name='admissionapplication',
            name='assigned_preference_order',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Número de preferencia que fue asignada (1 = primera opción)', null=True),
        ),
        migrations.AlterField(
            model_name='admissiondocument',
            name='status',
            field=models.CharField(choices=[('pending', 'Pendiente'), ('validated', 'Validado'), ('rejected', 'Rechazado')], default='pending', max_length=10),
        ),
    ]
