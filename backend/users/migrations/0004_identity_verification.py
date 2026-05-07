from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_dni_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='identity_verification_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='identity_verification_status',
            field=models.CharField(
                choices=[
                    ('unsubmitted', 'Unsubmitted'),
                    ('pending', 'Pending review'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='approved',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='identity_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='identity_reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='identity_reviews_performed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='IdentityVerificationDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='identity_verifications/')),
                (
                    'document_type',
                    models.CharField(
                        choices=[
                            ('identity', 'Identity document'),
                            ('supporting', 'Supporting evidence'),
                        ],
                        default='identity',
                        max_length=20,
                    ),
                ),
                ('original_filename', models.CharField(blank=True, max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='identity_documents',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Identity verification document',
                'verbose_name_plural': 'Identity verification documents',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
