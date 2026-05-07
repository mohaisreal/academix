from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_emailtemplate_systemsettings_email_footer_text_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='student_id_format',
            field=models.CharField(
                default=r'\d{6}',
                help_text=(
                    'Regex-like format for auto-generated student IDs. '
                    r'Use \d{N} for N random digits, [A-Z]{N} for N uppercase letters, '
                    'or a fixed prefix followed by one of those groups. '
                    r'Example: "STU-\d{6}" or "\d{6}"'
                ),
                max_length=60,
            ),
        ),
    ]
