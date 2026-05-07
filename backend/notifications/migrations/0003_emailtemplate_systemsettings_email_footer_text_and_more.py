# Generado por Django 5.2.12 el 2026-03-29 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_add_email_preferences_and_system_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True)),
                ('subject_template', models.CharField(max_length=255)),
                ('body_template', models.TextField()),
                ('description', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='email_footer_text',
            field=models.TextField(default='Academix - Academic Gestión System'),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='email_header_color',
            field=models.CharField(default='#4F46E5', max_length=7),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='email_logo_url',
            field=models.URLField(blank=True, default=''),
        ),
    ]
