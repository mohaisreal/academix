# Generado por Django 6.0.2 el 2026-03-23 14:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicperiod',
            name='enrollment_modification_deadline',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='career',
            name='total_spots',
            field=models.PositiveIntegerField(default=100),
        ),
    ]
