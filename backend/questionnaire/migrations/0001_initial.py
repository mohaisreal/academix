# Generado por Django 5.2.12 el 2026-03-31 15:32

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('academic', '0002_add_total_spots_and_deadline'),
        ('admissions', '0002_add_completed_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Questionnaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('flow_type', models.CharField(choices=[('admissions', 'Admissions'), ('enrollment', 'Enrollment')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('career', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questionnaires', to='academic.career')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_questionnaires', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='QuestionnaireResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted')], default='draft', max_length=20)),
                ('current_step', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('admission', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questionnaire_responses', to='admissions.admissionapplication')),
                ('questionnaire', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='responses', to='questionnaire.questionnaire')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questionnaire_responses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
                'unique_together': {('questionnaire', 'student')},
            },
        ),
        migrations.CreateModel(
            name='QuestionnaireStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('questionnaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='questionnaire.questionnaire')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=500)),
                ('help_text', models.TextField(blank=True)),
                ('question_type', models.CharField(choices=[('text', 'Text'), ('textarea', 'Textarea'), ('email', 'Email'), ('tel', 'Phone'), ('number', 'Number'), ('date', 'Date'), ('select', 'Select'), ('radio', 'Radio'), ('checkbox', 'Checkbox'), ('file_upload', 'File Upload'), ('career_select', 'Career Select'), ('subject_select', 'Subject Select'), ('stripe_payment', 'Stripe Payment'), ('info', 'Info')], max_length=30)),
                ('is_required', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('depends_on_value', models.CharField(blank=True, max_length=255)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('depends_on', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dependents', to='questionnaire.question')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='questionnaire.questionnairestep')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='QuestionOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='questionnaire.question')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='QuestionAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_value', models.TextField(blank=True, default='')),
                ('file_value', models.FileField(blank=True, null=True, upload_to='questionnaire_answers/')),
                ('json_value', models.JSONField(blank=True, null=True)),
                ('stripe_payment_intent_id', models.CharField(blank=True, max_length=255)),
                ('stripe_payment_status', models.CharField(blank=True, choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], max_length=20)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='answers', to='questionnaire.question')),
                ('response', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='questionnaire.questionnaireresponse')),
            ],
            options={
                'unique_together': {('response', 'question')},
            },
        ),
    ]
