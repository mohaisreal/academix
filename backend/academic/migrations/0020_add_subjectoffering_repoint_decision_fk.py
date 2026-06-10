"""
Schema migration:
1. Create SubjectOffering model.
2. Add nullable 'offering' FK to TeacherSubjectDecision.
3. Drop old UniqueConstraint on (teacher, subject, period).
4. Remove 'subject' FK from TeacherSubjectDecision.
5. Add new UniqueConstraint on (teacher, offering).
6. Update DECISION_CHOICES and default on TeacherSubjectDecision.decision.
7. Update decided_by limit_choices_to from role__in=['d','m'] to role='m'.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0019_delete_selected_decisions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Create SubjectOffering
        migrations.CreateModel(
            name='SubjectOffering',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_students', models.PositiveSmallIntegerField(default=30)),
                ('is_active', models.BooleanField(default=False)),
                ('label', models.CharField(blank=True, default='', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('department', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offerings',
                    to='academic.department',
                )),
                ('period', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offerings',
                    to='academic.academicperiod',
                )),
                ('subject', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offerings',
                    to='academic.subject',
                )),
            ],
            options={
                'ordering': ['period', 'subject', 'label'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('subject', 'period', 'label'),
                        name='unique_subject_period_label_offering',
                    ),
                ],
            },
        ),

        # 2. Add nullable offering FK to TeacherSubjectDecision
        migrations.AddField(
            model_name='teachersubjectdecision',
            name='offering',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teacher_decisions',
                to='academic.subjectoffering',
            ),
        ),

        # 3. Drop old UniqueConstraint (teacher, subject, period)
        migrations.RemoveConstraint(
            model_name='teachersubjectdecision',
            name='unique_teacher_subject_decision',
        ),

        # 4. Remove 'subject' FK from TeacherSubjectDecision
        migrations.RemoveField(
            model_name='teachersubjectdecision',
            name='subject',
        ),

        # 5a. Make offering non-nullable now that subject is gone
        migrations.AlterField(
            model_name='teachersubjectdecision',
            name='offering',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teacher_decisions',
                to='academic.subjectoffering',
            ),
        ),

        # 5b. Add new UniqueConstraint (teacher, offering)
        migrations.AddConstraint(
            model_name='teachersubjectdecision',
            constraint=models.UniqueConstraint(
                fields=('teacher', 'offering'),
                name='unique_teacher_offering_decision',
            ),
        ),

        # 6. Update decision choices and default
        migrations.AlterField(
            model_name='teachersubjectdecision',
            name='decision',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('selected', 'Selected'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=12,
            ),
        ),

        # 7. Update decided_by limit_choices_to
        migrations.AlterField(
            model_name='teachersubjectdecision',
            name='decided_by',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'role': 'm'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='made_subject_decisions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # 8. Update ordering in Meta (remove 'subject', add 'offering')
        migrations.AlterModelOptions(
            name='teachersubjectdecision',
            options={'ordering': ['period', 'offering', 'teacher']},
        ),
    ]
