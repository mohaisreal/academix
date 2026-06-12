from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('material', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
