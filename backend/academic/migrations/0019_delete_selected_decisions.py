"""
Data migration: delete all TeacherSubjectDecision rows where decision='selected'.
These rows referenced subjects directly; they cannot be mapped to SubjectOffering
records (which don't exist yet), so they are discarded after being snapshotted.
"""
from django.db import migrations


def delete_selected_decisions(apps, schema_editor):
    TeacherSubjectDecision = apps.get_model('academic', 'TeacherSubjectDecision')
    TeacherSubjectDecision.objects.filter(decision='selected').delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0018_snapshot_selected_decisions'),
    ]

    operations = [
        migrations.RunPython(delete_selected_decisions, noop),
    ]
