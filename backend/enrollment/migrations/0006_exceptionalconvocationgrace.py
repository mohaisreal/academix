from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enrollment', '0005_alter_enrollmentfee_status'),
        ('academic', '0015_subject_max_convocations'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExceptionalConvocationGrace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('granted_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='granted_convocation_graces', to='users.user')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='convocation_graces', to='academic.academicperiod')),
                ('student', models.ForeignKey(limit_choices_to={'role': 's'}, on_delete=django.db.models.deletion.CASCADE, related_name='convocation_graces', to='users.user')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='convocation_graces', to='academic.subject')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='exceptionalconvocationgrace',
            constraint=models.UniqueConstraint(fields=('student', 'subject', 'period'), name='unique_student_subject_period_grace'),
        ),
        migrations.AddIndex(
            model_name='exceptionalconvocationgrace',
            index=models.Index(fields=['student', 'subject', 'period', 'is_active'], name='grace_lookup_idx'),
        ),
        migrations.AddIndex(
            model_name='exceptionalconvocationgrace',
            index=models.Index(fields=['period', 'is_active'], name='grace_period_active_idx'),
        ),
    ]
