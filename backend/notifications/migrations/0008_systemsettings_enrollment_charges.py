from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0007_alter_useremailpreference_event_preferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='school_insurance_fee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Importe fijo de seguro escolar incluido en el pago de matrícula.',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='transcript_opening_fee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Importe fijo de apertura de expediente para alumnos sin matrículas previas.',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='enrollment_extra_charges',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Cobros extra de matrícula configurables. Formato: [{"label": "Carné universitario", "amount": "12.00", "active": true}]',
            ),
        ),
    ]
