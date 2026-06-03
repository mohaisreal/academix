from django.db import models
from django.conf import settings


NOTIFICATION_DELIVERY_PROFILE = 'profile'
NOTIFICATION_DELIVERY_EMAIL = 'email'
NOTIFICATION_DELIVERY_BOTH = 'both'

NOTIFICATION_THEME_DARK = 'dark'
NOTIFICATION_THEME_LIGHT = 'light'


NOTIFICATION_EVENT_DEFINITIONS = [
    {
        'key': 'grade_recorded',
        'label': 'Se te ha calificado una tarea',
        'description': 'Avisos cuando un profesor registra o actualiza una calificación.',
        'template_name': 'grade_recorded',
    },
    {
        'key': 'message_received',
        'label': 'Has recibido un mensaje',
        'description': 'Avisos cuando otro usuario te envía un mensaje interno.',
        'template_name': 'message_received',
    },
    {
        'key': 'material_added',
        'label': 'Se ha añadido un nuevo material a tu clase',
        'description': 'Avisos cuando un profesor publica material para una clase en la que estás inscrito.',
        'template_name': 'material_added',
    },
    {
        'key': 'admission_status',
        'label': 'Cambios en admisiones y plazas',
        'description': 'Resoluciones provisionales, definitivas, expiraciones y confirmaciones de plaza.',
        'template_name': 'admission_status',
    },
    {
        'key': 'enrollment_status',
        'label': 'Cambios en matrícula y clases',
        'description': 'Confirmaciones de matrícula, finalización del proceso y movimientos de clases.',
        'template_name': 'enrollment_status',
    },
    {
        'key': 'document_status',
        'label': 'Revisión de documentos',
        'description': 'Validaciones o rechazos de documentos de admisión.',
        'template_name': 'document_status',
    },
    {
        'key': 'waitlist_update',
        'label': 'Actualizaciones de lista de espera',
        'description': 'Avisos cuando se libera una plaza o cambia tu posición de espera.',
        'template_name': 'waitlist_update',
    },
]


NOTIFICATION_EVENT_ALIASES = {
    # Admissions
    'provisional_admitted': 'admission_status',
    'provisional_waitlisted': 'admission_status',
    'provisional_rejected': 'admission_status',
    'admission_resolved': 'admission_status',
    'admission_expired': 'admission_status',
    'rejected': 'admission_status',
    'waitlisted': 'waitlist_update',
    'waitlist': 'waitlist_update',

    # Documents
    'document_validated': 'document_status',
    'document_rejected': 'document_status',

    # Matrícula
    'enrollment_confirmed': 'enrollment_status',
    'enrollment_completed': 'enrollment_status',
    'class_waitlist_promoted': 'enrollment_status',

    # Academic activity
    'grade_recorded': 'grade_recorded',
    'message_received': 'message_received',
    'material_added': 'material_added',
}


def default_event_preferences():
    return {item['key']: True for item in NOTIFICATION_EVENT_DEFINITIONS}


class Notification(models.Model):
    TYPE_CHOICES = [
        ('info', 'Info'),
        ('success', 'Correcto'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=8, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=30, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class UserEmailPreference(models.Model):
    DELIVERY_CHOICES = [
        (NOTIFICATION_DELIVERY_PROFILE, 'Solo perfil'),
        (NOTIFICATION_DELIVERY_EMAIL, 'Email only'),
        (NOTIFICATION_DELIVERY_BOTH, 'Perfil y correo electrónico'),
    ]
    THEME_CHOICES = [
        (NOTIFICATION_THEME_DARK, 'Dark'),
        (NOTIFICATION_THEME_LIGHT, 'Light'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_preference'
    )
    notifications_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    delivery_channel = models.CharField(
        max_length=12,
        choices=DELIVERY_CHOICES,
        default=NOTIFICATION_DELIVERY_BOTH,
    )
    theme = models.CharField(
        max_length=8,
        choices=THEME_CHOICES,
        default=NOTIFICATION_THEME_DARK,
    )
    event_preferences = models.JSONField(default=default_event_preferences, blank=True)

    def __str__(self):
        return (
            f"{self.user.username}: notifications_enabled={self.notifications_enabled}, "
            f"delivery_channel={self.delivery_channel}, theme={self.theme}"
        )


class SystemSettings(models.Model):
    email_notifications_enabled = models.BooleanField(default=True)
    email_header_color = models.CharField(max_length=7, default='#4F46E5')
    email_logo_url = models.URLField(blank=True, default='')
    email_footer_text = models.TextField(default='Academix - Academic Gestión System')
    student_id_format = models.CharField(
        max_length=60,
        default=r'\d{6}',
        help_text=(
            'Regex-like format for auto-generated student IDs. '
            r'Use \d{N} for N random digits, [A-Z]{N} for N uppercase letters, '
            'or a fixed prefix followed by one of those groups. '
            r'Example: "STU-\d{6}" or "\d{6}"'
        ),
    )
    admission_public_dni_mask_regex = models.CharField(
        max_length=120,
        default=r'^(.{3}).*(.{2})$',
        help_text='Regex usado para enmascarar DNI/NIE en las listas públicas de admisión.',
    )
    admission_public_dni_mask_replacement = models.CharField(
        max_length=120,
        default=r'\1****\2',
        help_text='Reemplazo regex aplicado al DNI/NIE antes de publicarlo.',
    )
    school_insurance_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text='Importe fijo de seguro escolar incluido en el pago de matrícula.',
    )
    transcript_opening_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text='Importe fijo de apertura de expediente para alumnos sin matrículas previas.',
    )
    admission_waitlist_grace_days = models.PositiveIntegerField(
        default=7,
        help_text='Días de gracia para que un admitido en lista de espera complete la matrícula.',
    )
    enrollment_extra_charges = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Cobros extra de matrícula configurables. Formato: '
            '[{"label": "Carné universitario", "amount": "12.00", "active": true}]'
        ),
    )

    class Meta:
        verbose_name = 'Configuración del sistema'
        verbose_name_plural = 'Configuración del sistema'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("SystemSettings singleton cannot be deleted.")

    def __str__(self):
        return f"SystemSettings (email_notifications_enabled={self.email_notifications_enabled})"


class EmailTemplate(models.Model):
    name = models.CharField(max_length=60, unique=True)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
