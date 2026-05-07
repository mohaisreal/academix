from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0001_initial_admissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='admissionapplication',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('submitted', 'Submitted'),
                    ('under_review', 'Under Review'),
                    ('admitted', 'Admitted'),
                    ('waitlisted', 'Waitlisted'),
                    ('rejected', 'Rejected'),
                    ('confirmed', 'Confirmed'),
                    ('completed', 'Completed'),
                    ('withdrawn', 'Withdrawn'),
                    ('expired', 'Expired'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
