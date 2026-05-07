from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0004_academicperiod_admission_window'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='credit_price_first_enrollment',
            field=models.DecimalField(
                decimal_places=2,
                default=16.00,
                help_text='Precio por crédito para la 1ª matrícula de esta asignatura.',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='credit_price_second_enrollment',
            field=models.DecimalField(
                decimal_places=2,
                default=28.00,
                help_text='Precio por crédito para la 2ª matrícula de esta asignatura.',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='credit_price_third_enrollment',
            field=models.DecimalField(
                decimal_places=2,
                default=45.00,
                help_text='Precio por crédito para la 3ª matrícula de esta asignatura.',
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='credit_price_fourth_or_more_enrollment',
            field=models.DecimalField(
                decimal_places=2,
                default=60.00,
                help_text='Precio por crédito para la 4ª matrícula o posteriores de esta asignatura.',
                max_digits=8,
            ),
        ),
    ]
