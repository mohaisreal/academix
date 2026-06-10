"""
Data migration: snapshot all TeacherSubjectDecision rows with decision='selected'
to a JSON file for rollback safety, then log the count.
"""
import json
import os
from django.db import migrations


def snapshot_selected_decisions(apps, schema_editor):
    TeacherSubjectDecision = apps.get_model('academic', 'TeacherSubjectDecision')
    rows = list(
        TeacherSubjectDecision.objects.filter(decision='selected').values(
            'id', 'teacher_id', 'subject_id', 'period_id', 'decision', 'notes'
        )
    )
    if not rows:
        return

    snapshot_path = os.path.join(
        os.path.dirname(__file__), 'snapshot_selected_decisions.json'
    )
    with open(snapshot_path, 'w', encoding='utf-8') as fh:
        json.dump(rows, fh, indent=2, default=str)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0017_phase1_teacher_selection_schema'),
    ]

    operations = [
        migrations.RunPython(snapshot_selected_decisions, noop),
    ]
