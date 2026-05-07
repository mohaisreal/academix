# Generado por Django 6.0.2 el 2026-03-23 14:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_user_options_alter_user_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='dni',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
