from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0002_add_completed_status'),
        ('academic', '0001_initial'),
    ]

    operations = [
        # 1. Agregar nuevos campos a AdmissionApplication
        migrations.AddField(
            model_name='admissionapplication',
            name='access_route',
            field=models.CharField(
                blank=True,
                choices=[
                    ('evau', 'EvAU / EBAU (Bachillerato + Selectividad)'),
                    ('fp', 'Ciclo Formativo de Grado Superior (FP)'),
                    ('titulado', 'Titulado Universitario'),
                    ('mayores_25', 'Mayores de 25 años'),
                    ('mayores_40', 'Mayores de 40 años'),
                    ('mayores_45', 'Mayores de 45 años'),
                    ('internacional', 'Acceso Internacional / Homologación'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='bachillerato_grade',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=4, null=True,
                help_text='Nota media de Bachillerato o Ciclo Formativo (0.000 – 10.000)',
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='evau_obligatory_grade',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=4, null=True,
                help_text='Nota de la fase obligatoria de la EvAU (0.000 – 10.000)',
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='evau_voluntary_subjects',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Asignaturas y notas de la fase voluntaria de la EvAU',
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='admission_score',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=5, null=True,
                help_text='Nota de admisión calculada (hasta 14.000)',
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='assigned_career',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_admissions',
                to='academic.career',
                help_text='Carrera asignada en la resolución',
            ),
        ),
        migrations.AddField(
            model_name='admissionapplication',
            name='assigned_preference_order',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text='Número de preferencia que fue asignada',
            ),
        ),

        # 2. Actualizar opciones de status (ampliar max_length y opciones)
        migrations.AlterField(
            model_name='admissionapplication',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Borrador'),
                    ('submitted', 'Enviada'),
                    ('under_review', 'En Revisión'),
                    ('provisional_admitted', 'Admitida Provisionalmente'),
                    ('provisional_waitlisted', 'Lista de Espera Provisional'),
                    ('provisional_rejected', 'No Admitida Provisionalmente'),
                    ('admitted', 'Admitida Definitivamente'),
                    ('waitlisted', 'Lista de Espera'),
                    ('rejected', 'No Admitida'),
                    ('confirmed', 'Plaza Confirmada'),
                    ('completed', 'Completada'),
                    ('withdrawn', 'Renunciada'),
                    ('expired', 'Expirada'),
                ],
                default='draft',
                max_length=30,
            ),
        ),

        # 3. Quitar la FK career (nullable primero, luego quitar unique_together, luego eliminar)
        migrations.AlterField(
            model_name='admissionapplication',
            name='career',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='academic.career',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='admissionapplication',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='admissionapplication',
            name='career',
        ),

        # 4. Nueva unique_together (student, academic_period)
        migrations.AlterUniqueTogether(
            name='admissionapplication',
            unique_together={('student', 'academic_period')},
        ),

        # 5. Actualizar document_type max_length y choices
        migrations.AlterField(
            model_name='admissiondocument',
            name='document_type',
            field=models.CharField(
                choices=[
                    ('id_document', 'DNI / NIE / Pasaporte'),
                    ('evau_credential', 'Credencial EvAU / EBAU'),
                    ('bachillerato_certificate', 'Certificado de Notas de Bachillerato'),
                    ('fp_title', 'Título de FP / Ciclo Formativo'),
                    ('university_degree', 'Título Universitario'),
                    ('disability_certificate', 'Certificado de Discapacidad'),
                    ('large_family', 'Título de Familia Numerosa'),
                    ('academic_record', 'Expediente Académico'),
                    ('other', 'Otro Documento'),
                ],
                max_length=30,
            ),
        ),

        # 6. Crear modelo AdmissionPreference
        migrations.CreateModel(
            name='AdmissionPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('preference_order', models.PositiveSmallIntegerField(
                    help_text='Orden de preferencia, 1 = primera opción',
                )),
                ('is_assigned', models.BooleanField(
                    default=False,
                    help_text='True cuando esta preferencia fue la asignada en la resolución',
                )),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preferences',
                    to='admissions.admissionapplication',
                )),
                ('career', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='academic.career',
                )),
            ],
            options={
                'ordering': ['preference_order'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='admissionpreference',
            unique_together={
                ('application', 'career'),
                ('application', 'preference_order'),
            },
        ),
    ]
