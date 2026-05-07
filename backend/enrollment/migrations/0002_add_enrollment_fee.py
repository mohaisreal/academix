# Generado por Django 6.0.2 el 2026-03-23 14:10

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrollment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnrollmentFee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('discount_reason', models.CharField(blank=True, max_length=200)),
                ('final_amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('exempted', 'Exempted')], default='pending', max_length=10)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('career_enrollment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='fee', to='enrollment.careerenrollment')),
            ],
            options={
                'ordering': ['-career_enrollment__enrolled_at'],
            },
        ),
    ]
