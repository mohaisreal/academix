# Generado por Django 5.2.12 el 2026-03-31 21:02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrollment', '0002_add_enrollment_fee'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentBenefit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('benefit_type', models.CharField(choices=[('familia_numerosa_general', 'Familia Numerosa General'), ('familia_numerosa_especial', 'Familia Numerosa Especial'), ('discapacidad_33', 'Discapacidad ≥ 33%'), ('beca_mec', 'Beca MEC')], max_length=30)),
                ('verified', models.BooleanField(default=False, help_text='Solo los beneficios verificados por administración se aplican al cálculo.')),
                ('valid_until', models.DateField(blank=True, help_text='Fecha de vencimiento. Nulo = vigencia indefinida (ej: discapacidad).', null=True)),
                ('student', models.ForeignKey(limit_choices_to={'role': 's'}, on_delete=django.db.models.deletion.CASCADE, related_name='benefits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['benefit_type'],
                'unique_together': {('student', 'benefit_type')},
            },
        ),
    ]
