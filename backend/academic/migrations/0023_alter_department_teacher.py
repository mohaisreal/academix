from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0022_class_grade_visibility_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='department',
            name='teacher',
            field=models.OneToOneField(blank=True, limit_choices_to={'role': 't'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='headed_department', to=settings.AUTH_USER_MODEL),
        ),
    ]
