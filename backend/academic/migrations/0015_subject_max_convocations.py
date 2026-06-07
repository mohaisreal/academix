from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0014_backfill_generated_class_teachers'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='max_convocations',
            field=models.PositiveSmallIntegerField(
                default=6,
                help_text='Número máximo de convocatorias fallidas permitidas antes de bloquear la matrícula.',
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
