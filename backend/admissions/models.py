from django.db import models


class AdmissionApplication(models.Model):
    ACCESS_ROUTE_CHOICES = [
        ('evau', 'EvAU / EBAU (Bachillerato + Selectividad)'),
        ('fp', 'Ciclo Formativo de Grado Superior (FP)'),
        ('titulado', 'Titulado Universitario'),
        ('mayores_25', 'Mayores de 25 años'),
        ('mayores_40', 'Mayores de 40 años'),
        ('mayores_45', 'Mayores de 45 años'),
        ('internacional', 'Acceso Internacional / Homologación'),
    ]

    STATUS_CHOICES = [
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
    ]

    student = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='admission_applications'
    )
    academic_period = models.ForeignKey(
        'academic.AcademicPeriod',
        on_delete=models.CASCADE
    )

    # Vía de acceso
    access_route = models.CharField(
        max_length=20,
        choices=ACCESS_ROUTE_CHOICES,
        blank=True,
    )

    # Datos académicos
    bachillerato_grade = models.DecimalField(
        max_digits=4, decimal_places=3,
        null=True, blank=True,
        help_text='Nota media de Bachillerato o Ciclo Formativo (0.000 – 10.000)'
    )
    evau_obligatory_grade = models.DecimalField(
        max_digits=4, decimal_places=3,
        null=True, blank=True,
        help_text='Nota de la fase obligatoria de la EvAU (0.000 – 10.000)'
    )
    # Lista de {subject: str, grade: float} para la fase voluntaria
    evau_voluntary_subjects = models.JSONField(
        default=list, blank=True,
        help_text='Asignaturas y notas de la fase voluntaria de la EvAU'
    )
    admission_score = models.DecimalField(
        max_digits=5, decimal_places=3,
        null=True, blank=True,
        help_text='Nota de admisión calculada (hasta 14.000)'
    )

    # Resultado: carrera asignada y preferencia elegida
    assigned_career = models.ForeignKey(
        'academic.Career',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_admissions',
        help_text='Carrera asignada en la resolución'
    )
    assigned_preference_order = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Número de preferencia que fue asignada (1 = primera opción)'
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    submission_date = models.DateTimeField(null=True, blank=True)
    admission_expiry_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        career = self.assigned_career.name if self.assigned_career else '—'
        return f"{self.student} → {self.academic_period} / {career} ({self.status})"

    def calculate_admission_score(self):
        """
        Fórmula española: NMB * 0.6 + NMEvAU * 0.4 + bonus fase voluntaria.
        El bonus es la suma de max(0, nota_mat - 5) * peso para cada asignatura
        (máx 2 asignaturas voluntarias cuentan, peso 0.1 o 0.2 según parametrización).
        Aquí usamos peso 0.2 por asignatura, máx 2 asignaturas → hasta +4 puntos extra.
        Resultado máx: 10 puntos base + 4 puntos voluntarios = 14.
        """
        if self.bachillerato_grade is None or self.evau_obligatory_grade is None:
            return None

        base = float(self.bachillerato_grade) * 0.6 + float(self.evau_obligatory_grade) * 0.4

        bonus = 0.0
        subjects = self.evau_voluntary_subjects or []
        counted = 0
        for s in subjects:
            if counted >= 2:
                break
            grade = float(s.get('grade', 0))
            if grade >= 5:
                bonus += (grade - 5) * 0.2
                counted += 1

        return round(min(base + bonus, 14.0), 3)


class AdmissionPreference(models.Model):
    """Titulaciones solicitadas ordenadas por preferencia (hasta 10)."""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('admitted', 'Admitida'),
        ('waitlisted', 'Lista de espera'),
        ('rejected', 'No admitida'),
        ('withdrawn', 'Renunciada'),
    ]

    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    career = models.ForeignKey(
        'academic.Career',
        on_delete=models.CASCADE
    )
    preference_order = models.PositiveSmallIntegerField(
        help_text='Orden de preferencia, 1 = primera opción'
    )
    is_assigned = models.BooleanField(
        default=False,
        help_text='True cuando esta preferencia fue la asignada en la resolución'
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    ranking_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Puntuación usada para ordenar esta preferencia en la resolución.',
    )
    rank_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Posición absoluta en la lista publicada de esta titulación.',
    )
    waitlist_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Posición en lista de espera, si aplica.',
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha de publicación pública de este resultado.',
    )
    draft_result_status = models.CharField(
        max_length=12,
        choices=[
            ('admitted', 'Admitida'),
            ('waitlisted', 'Lista de espera'),
        ],
        null=True,
        blank=True,
        help_text='Resultado calculado en el último borrador de ranking, aún no publicado.',
    )
    draft_ranking_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Puntuación calculada en el último borrador de ranking.',
    )
    draft_rank_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Posición absoluta calculada en el último borrador de ranking.',
    )
    draft_waitlist_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Posición en lista de espera calculada en el último borrador de ranking.',
    )
    draft_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha de generación del último borrador de ranking.',
    )

    class Meta:
        unique_together = [
            ('application', 'career'),
            ('application', 'preference_order'),
        ]
        ordering = ['preference_order']

    def __str__(self):
        return f"{self.application} — {self.preference_order}. {self.career}"


class AdmissionDocument(models.Model):
    TYPE_CHOICES = [
        ('id_document', 'DNI / NIE / Pasaporte'),
        ('evau_credential', 'Credencial EvAU / EBAU'),
        ('bachillerato_certificate', 'Certificado de Notas de Bachillerato'),
        ('fp_title', 'Título de FP / Ciclo Formativo'),
        ('university_degree', 'Título Universitario'),
        ('disability_certificate', 'Certificado de Discapacidad'),
        ('large_family', 'Título de Familia Numerosa'),
        ('academic_record', 'Expediente Académico'),
        ('other', 'Otro Documento'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('validated', 'Validado'),
        ('rejected', 'Rechazado'),
    ]

    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    file = models.FileField(upload_to='admissions/documents/%Y/%m/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', '-uploaded_at']

    def __str__(self):
        return f"{self.application} — {self.document_type} ({self.status})"
