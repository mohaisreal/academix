from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0011_scheduleassignment_multisession'),
    ]

    operations = [
        migrations.AddField(
            model_name='class',
            name='is_generated_by_timetable',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
