from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_profile_notification_preferences_and_default_templates'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='admission_public_dni_mask_regex',
            field=models.CharField(
                default='^(.{3}).*(.{2})$',
                help_text='Regex usado para enmascarar DNI/NIE en las listas públicas de admisión.',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='admission_public_dni_mask_replacement',
            field=models.CharField(
                default='\\1****\\2',
                help_text='Reemplazo regex aplicado al DNI/NIE antes de publicarlo.',
                max_length=120,
            ),
        ),
    ]
