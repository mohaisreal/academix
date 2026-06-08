from django.db import migrations, models
import django.db.models.deletion


def _section_label_for_index(index):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    value = index + 1
    label = ''
    while value:
        value, remainder = divmod(value - 1, 26)
        label = alphabet[remainder] + label
    return label


def backfill_class_section_labels(apps, schema_editor):
    Class = apps.get_model('academic', 'Class')

    grouped = {}
    for cls in Class.objects.order_by('period_id', 'subject_id', 'id').only('id', 'period_id', 'subject_id', 'section_label'):
        grouped.setdefault((cls.period_id, cls.subject_id), []).append(cls.id)

    for ids in grouped.values():
        for index, class_id in enumerate(ids):
            Class.objects.filter(id=class_id).update(section_label=_section_label_for_index(index))


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0016_subject_career_shared_relation'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherSubjectDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision', models.CharField(choices=[('approve', 'Approve'), ('reject', 'Reject'), ('none', 'None')], default='none', max_length=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_decisions', to='academic.academicperiod')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_decisions', to='academic.subject')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 't'}, on_delete=django.db.models.deletion.CASCADE, related_name='subject_decisions', to='users.user')),
                ('decided_by', models.ForeignKey(blank=True, limit_choices_to={'role__in': ['d', 'm']}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='made_subject_decisions', to='users.user')),
            ],
            options={
                'ordering': ['period', 'subject', 'teacher'],
                'constraints': [
                    models.UniqueConstraint(fields=('teacher', 'subject', 'period'), name='unique_teacher_subject_decision'),
                ],
            },
        ),
        migrations.CreateModel(
            name='TeacherSubjectEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_eligible', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_eligibilities', to='academic.academicperiod')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_eligibilities', to='academic.subject')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 't'}, on_delete=django.db.models.deletion.CASCADE, related_name='subject_eligibilities', to='users.user')),
                ('reviewed_by', models.ForeignKey(blank=True, limit_choices_to={'role__in': ['d', 'm']}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_subject_eligibilities', to='users.user')),
            ],
            options={
                'ordering': ['period', 'subject', 'teacher'],
                'constraints': [
                    models.UniqueConstraint(fields=('teacher', 'subject', 'period'), name='unique_teacher_subject_eligibility'),
                ],
            },
        ),
        migrations.AddField(
            model_name='class',
            name='section_label',
            field=models.CharField(default='A', max_length=10),
        ),
        migrations.AddField(
            model_name='class',
            name='source_teacher_decision',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_classes', to='academic.teachersubjectdecision'),
        ),
        migrations.RunPython(backfill_class_section_labels, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='class',
            name='unique_period_subject_class',
        ),
        migrations.AddConstraint(
            model_name='class',
            constraint=models.UniqueConstraint(fields=('period', 'subject', 'section_label'), name='unique_period_subject_section_class'),
        ),
    ]
