from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrollment', '0003_studentbenefit'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollmentfee',
            name='line_items',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='enrollmentfee',
            name='stripe_payment_intent_id',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='enrollmentfee',
            name='stripe_payment_status',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='enrollmentfee',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('paid', 'Paid'),
                    ('exempted', 'Exempted'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=10,
            ),
        ),
    ]
