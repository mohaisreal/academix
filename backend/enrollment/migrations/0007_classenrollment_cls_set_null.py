from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enrollment', '0006_exceptionalconvocationgrace'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classenrollment',
            name='cls',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enrollments', to='academic.class'),
        ),
    ]
