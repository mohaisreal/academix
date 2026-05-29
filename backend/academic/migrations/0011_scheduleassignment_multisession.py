from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0010_unique_period_subject_class'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='scheduleassignment',
            name='unique_run_class_assignment',
        ),
        migrations.AddConstraint(
            model_name='scheduleassignment',
            constraint=models.UniqueConstraint(fields=('run', 'cls', 'slot'), name='unique_run_class_slot'),
        ),
    ]
