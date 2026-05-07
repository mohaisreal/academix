from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaire', '0003_preinscripcion_template'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='questionnaireresponse',
            unique_together=set(),
        ),
    ]
