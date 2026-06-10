"""
Schema migration: drop the TeacherSubjectEligibility table entirely.
The eligibility concept is replaced by SubjectOffering.is_active.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0020_add_subjectoffering_repoint_decision_fk'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TeacherSubjectEligibility',
        ),
    ]
