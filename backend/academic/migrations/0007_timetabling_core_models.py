from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0006_alter_career_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TimetableRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('completed', 'Completed'), ('partial', 'Partial'), ('failed', 'Failed'), ('published', 'Published')], default='draft', max_length=12)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_runs', to='academic.academicperiod')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='TimeSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])) ,
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='time_slots', to='academic.academicperiod')),
            ],
            options={'ordering': ['day_of_week', 'start_time']},
        ),
        migrations.CreateModel(
            name='ScheduleAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('generated', 'Generated'), ('manual', 'Manual')], default='generated', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('classroom', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='academic.classroom')),
                ('cls', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedule_assignments', to='academic.class')),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='academic.timetablerun')),
                ('slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='academic.timeslot')),
                ('teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_schedule_assignments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ConstraintViolation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('severity', models.CharField(choices=[('hard', 'Hard'), ('soft', 'Soft')], max_length=10)),
                ('reason', models.CharField(max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assignment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='violations', to='academic.scheduleassignment')),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='violations', to='academic.timetablerun')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='timeslot',
            constraint=models.UniqueConstraint(fields=('period', 'day_of_week', 'start_time', 'end_time'), name='unique_period_timeslot'),
        ),
        migrations.AddConstraint(
            model_name='scheduleassignment',
            constraint=models.UniqueConstraint(fields=('run', 'cls'), name='unique_run_class_assignment'),
        ),
        migrations.AddConstraint(
            model_name='scheduleassignment',
            constraint=models.UniqueConstraint(fields=('run', 'slot', 'classroom'), name='unique_run_slot_classroom'),
        ),
        migrations.AddConstraint(
            model_name='scheduleassignment',
            constraint=models.UniqueConstraint(fields=('run', 'slot', 'teacher'), name='unique_run_slot_teacher'),
        ),
    ]
