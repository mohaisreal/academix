from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0005_application_repeats_and_preference_results'),
    ]

    operations = [
        migrations.AddField(
            model_name='admissionpreference',
            name='draft_result_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('admitted', 'Admitida'),
                    ('waitlisted', 'Lista de espera'),
                ],
                help_text='Resultado calculado en el último borrador de ranking, aún no publicado.',
                max_length=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='draft_ranking_score',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='Puntuación calculada en el último borrador de ranking.',
                max_digits=7,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='draft_rank_position',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Posición absoluta calculada en el último borrador de ranking.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='draft_waitlist_position',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Posición en lista de espera calculada en el último borrador de ranking.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='draft_generated_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Fecha de generación del último borrador de ranking.',
                null=True,
            ),
        ),
    ]
