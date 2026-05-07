from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaire', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionnaire',
            name='is_preinscripcion_wizard',
            field=models.BooleanField(
                default=False,
                help_text='Si está marcado, este cuestionario reemplaza el asistente estático de preinscripción.',
            ),
        ),
    ]
