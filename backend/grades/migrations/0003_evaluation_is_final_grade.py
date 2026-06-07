from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0002_evaluation_weight'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='is_final_grade',
            field=models.BooleanField(default=False, help_text='Indica si esta evaluación representa la nota final que cuenta para convocatorias.'),
        ),
    ]
