from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0004_alter_admissionapplication_assigned_preference_order_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='admissionapplication',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendiente'),
                    ('admitted', 'Admitida'),
                    ('waitlisted', 'Lista de espera'),
                    ('rejected', 'No admitida'),
                    ('withdrawn', 'Renunciada'),
                ],
                default='pending',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='ranking_score',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text='Puntuación usada para ordenar esta preferencia en la resolución.',
                max_digits=7,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='rank_position',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Posición absoluta en la lista publicada de esta titulación.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='waitlist_position',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Posición en lista de espera, si aplica.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='admissionpreference',
            name='published_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Fecha de publicación pública de este resultado.',
                null=True,
            ),
        ),
    ]
