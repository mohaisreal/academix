# Generado por Django 5.2.11 el 2026-02-23 20:18

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('academic', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='materials/')),
                ('url', models.URLField(blank=True)),
                ('type', models.CharField(choices=[('document', 'Document'), ('video', 'Video'), ('link', 'Link'), ('other', 'Other')], default='document', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cls', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='academic.class')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
