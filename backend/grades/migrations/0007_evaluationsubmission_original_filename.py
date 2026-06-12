from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0006_alter_evaluation_min_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluationsubmission',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
