from django.db import migrations


def backfill_generated_class_teachers(apps, schema_editor):
    Class = apps.get_model('academic', 'Class')
    ScheduleAssignment = apps.get_model('academic', 'ScheduleAssignment')

    for cls in Class.objects.filter(is_generated_by_timetable=True, teacher__isnull=True).order_by('id'):
        teacher_ids = list(
            ScheduleAssignment.objects.filter(run__status='published', cls_id=cls.id)
            .exclude(teacher__isnull=True)
            .values_list('teacher_id', flat=True)
            .distinct()
        )
        if len(teacher_ids) == 1:
            cls.teacher_id = teacher_ids[0]
            cls.save(update_fields=['teacher'])


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0013_alter_classschedule_day_of_week_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_generated_class_teachers, migrations.RunPython.noop),
    ]
