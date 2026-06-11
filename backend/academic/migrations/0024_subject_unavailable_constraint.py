from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0023_alter_department_teacher'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schedulingconstraint',
            name='kind',
            field=models.CharField(choices=[('teacher_unavailable', 'Teacher unavailable'), ('classroom_unavailable', 'Classroom unavailable'), ('subject_unavailable', 'Subject unavailable')], max_length=24),
        ),
        migrations.AddField(
            model_name='schedulingconstraint',
            name='subject',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='scheduling_constraints', to='academic.subject'),
        ),
        migrations.AddField(
            model_name='schedulingconstraint',
            name='run',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='scheduling_constraints', to='academic.timetablerun'),
        ),
        migrations.RemoveField(
            model_name='schedulingconstraint',
            name='career',
        ),
    ]
