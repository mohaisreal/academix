from django.db import migrations, models
from django.db.models import Count


def validate_no_duplicate_period_subject(apps, schema_editor):
    Class = apps.get_model('academic', 'Class')
    duplicates = (
        Class.objects.values('period_id', 'subject_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    if duplicates.exists():
        first = duplicates.first()
        raise RuntimeError(
            'Cannot add unique_period_subject_class constraint. '
            f"Duplicate classes found for period_id={first['period_id']} "
            f"subject_id={first['subject_id']}."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0009_department_subject_department'),
    ]

    operations = [
        migrations.RunPython(validate_no_duplicate_period_subject, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='class',
            constraint=models.UniqueConstraint(fields=('period', 'subject'), name='unique_period_subject_class'),
        ),
    ]
