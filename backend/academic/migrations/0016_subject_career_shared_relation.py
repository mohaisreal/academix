from django.db import migrations, models
import django.db.models.deletion


def backfill_subject_careers(apps, schema_editor):
    Subject = apps.get_model('academic', 'Subject')
    SubjectCareer = apps.get_model('academic', 'SubjectCareer')

    relations = []
    for subject in Subject.objects.exclude(career_id__isnull=True).only('id', 'career_id'):
        relations.append(SubjectCareer(subject_id=subject.id, career_id=subject.career_id))

    SubjectCareer.objects.bulk_create(relations, ignore_conflicts=True)


def reverse_backfill_subject_careers(apps, schema_editor):
    SubjectCareer = apps.get_model('academic', 'SubjectCareer')
    SubjectCareer.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0015_subject_max_convocations'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubjectCareer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('career', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic.career')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic.subject')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('subject', 'career'), name='unique_subject_career_relation'),
                ],
            },
        ),
        migrations.AlterField(
            model_name='subject',
            name='career',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='legacy_subjects', to='academic.career'),
        ),
        migrations.AddField(
            model_name='subject',
            name='careers',
            field=models.ManyToManyField(related_name='subjects', through='academic.SubjectCareer', to='academic.career'),
        ),
        migrations.RunPython(backfill_subject_careers, reverse_backfill_subject_careers),
    ]
