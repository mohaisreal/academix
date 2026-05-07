# Generado por Django 6.0.2 el 2026-03-23 14:05

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('academic', '0002_add_total_spots_and_deadline'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdmissionApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('admitted', 'Admitted'), ('waitlisted', 'Waitlisted'), ('rejected', 'Rejected'), ('confirmed', 'Confirmed'), ('withdrawn', 'Withdrawn'), ('expired', 'Expired')], default='draft', max_length=20)),
                ('submission_date', models.DateTimeField(blank=True, null=True)),
                ('admission_expiry_date', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('academic_period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic.academicperiod')),
                ('career', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic.career')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='admission_applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('student', 'career', 'academic_period')},
            },
        ),
        migrations.CreateModel(
            name='AdmissionDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(choices=[('academic_record', 'Academic Record'), ('id_document', 'ID Document'), ('access_exam', 'Access Exam'), ('photo', 'Photo'), ('other', 'Other')], max_length=20)),
                ('file', models.FileField(upload_to='admissions/documents/%Y/%m/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('validated', 'Validated'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('rejection_reason', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='admissions.admissionapplication')),
            ],
            options={
                'ordering': ['document_type', '-uploaded_at'],
            },
        ),
    ]
