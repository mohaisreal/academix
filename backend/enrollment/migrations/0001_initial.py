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
            name='CareerEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('active', 'Active'), ('completed', 'Completed'), ('dropped', 'Dropped')], default='pending', max_length=10)),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('career', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='academic.career')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='academic.academicperiod')),
                ('student', models.ForeignKey(limit_choices_to={'role': 's'}, on_delete=django.db.models.deletion.CASCADE, related_name='career_enrollments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-enrolled_at'],
                'unique_together': {('student', 'career', 'period')},
            },
        ),
        migrations.CreateModel(
            name='ClassEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('enrolled', 'Enrolled'), ('dropped', 'Dropped'), ('waitlisted', 'Waitlisted')], default='enrolled', max_length=12)),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('cls', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='academic.class')),
                ('student', models.ForeignKey(limit_choices_to={'role': 's'}, on_delete=django.db.models.deletion.CASCADE, related_name='class_enrollments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-enrolled_at'],
                'unique_together': {('student', 'cls')},
            },
        ),
    ]
