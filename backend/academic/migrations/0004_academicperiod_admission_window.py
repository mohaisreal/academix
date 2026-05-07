# Generado manualmente — añade campos DateTimeField de ventana de admisión a AcademicPeriod

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0003_matriculaconfig_class_passing_grade_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicperiod',
            name='admission_open_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='academicperiod',
            name='admission_close_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
