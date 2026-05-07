# Generado manualmente para preferencias de notificación del perfil y plantillas de correo de eventos.

from django.db import migrations, models


def _default_event_preferences():
    return {
        'grade_recorded': True,
        'message_received': True,
        'material_added': True,
        'admission_status': True,
        'enrollment_status': True,
        'document_status': True,
        'waitlist_update': True,
    }


DEFAULT_TEMPLATES = [
    (
        'notification_default',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>{{message}}</p>'
                '<p>Entra en {{app_name}} para revisar los detalles.</p>'
            ),
            'description': 'Plantilla genérica para notificaciones del sistema.',
            'is_active': True,
        },
    ),
    (
        'grade_recorded',
        {
            'subject_template': 'Nueva calificación disponible: {{evaluation_name}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>Se ha registrado o actualizado tu calificación en '
                '<strong>{{subject_name}}</strong>.</p>'
                '<p><strong>Evaluación:</strong> {{evaluation_name}}<br />'
                '<strong>Calificación:</strong> {{score}} / {{max_score}}</p>'
                '<p>{{feedback}}</p>'
                '<p>Consulta tu perfil académico en {{app_name}} para ver el detalle completo.</p>'
            ),
            'description': 'Se envía cuando un profesor registra o actualiza una calificación.',
            'is_active': True,
        },
    ),
    (
        'message_received',
        {
            'subject_template': 'Nuevo mensaje de {{sender_name}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>Has recibido un nuevo mensaje interno.</p>'
                '<p><strong>De:</strong> {{sender_name}}<br />'
                '<strong>Asunto:</strong> {{message_subject}}</p>'
                '<p>{{message_preview}}</p>'
                '<p>Accede a {{app_name}} para responder.</p>'
            ),
            'description': 'Se envía cuando un usuario recibe un mensaje interno.',
            'is_active': True,
        },
    ),
    (
        'material_added',
        {
            'subject_template': 'Nuevo material en {{subject_name}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>Se ha añadido nuevo material a tu clase de '
                '<strong>{{subject_name}}</strong>.</p>'
                '<p><strong>Material:</strong> {{material_title}}<br />'
                '<strong>Publicado por:</strong> {{uploaded_by}}</p>'
                '<p>Entra en {{app_name}} para consultarlo.</p>'
            ),
            'description': 'Se envía cuando se publica material en una clase inscrita.',
            'is_active': True,
        },
    ),
    (
        'admission_status',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>{{message}}</p>'
                '<p>Revisa tu solicitud en {{app_name}}.</p>'
            ),
            'description': 'Se envía para resoluciones y cambios relevantes de admisión.',
            'is_active': True,
        },
    ),
    (
        'enrollment_status',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>{{message}}</p>'
                '<p>Revisa tu matrícula en {{app_name}}.</p>'
            ),
            'description': 'Se envía para confirmaciones y cambios de matrícula.',
            'is_active': True,
        },
    ),
    (
        'document_status',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>{{message}}</p>'
                '<p>Revisa tus documentos en {{app_name}}.</p>'
            ),
            'description': 'Se envía para validaciones o rechazos de documentos.',
            'is_active': True,
        },
    ),
    (
        'waitlist_update',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>{{message}}</p>'
                '<p>Accede a {{app_name}} para actuar antes de que expire el plazo.</p>'
            ),
            'description': 'Se envía cuando hay novedades en lista de espera.',
            'is_active': True,
        },
    ),
    (
        'email_verification',
        {
            'subject_template': '{{title}}',
            'body_template': (
                '<p>Hola {{user_name}},</p>'
                '<p>Activa tu cuenta de {{app_name}} desde el siguiente enlace:</p>'
                '<p><a href="{{verification_url}}">Verificar cuenta</a></p>'
                '<p>Este enlace expira en 3 días.</p>'
            ),
            'description': 'Se envía para verificar la cuenta después del registro.',
            'is_active': True,
        },
    ),
]


def seed_default_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('notifications', 'EmailTemplate')
    for name, defaults in DEFAULT_TEMPLATES:
        EmailTemplate.objects.get_or_create(name=name, defaults=defaults)


def sync_legacy_email_preferences(apps, schema_editor):
    UserEmailPreference = apps.get_model('notifications', 'UserEmailPreference')
    UserEmailPreference.objects.filter(email_enabled=False).update(delivery_channel='profile')


def noop_reverse(apps, schema_editor):
    # No elimines plantillas en migraciones inversas; los administradores pueden haberlas editado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_systemsettings_student_id_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='useremailpreference',
            name='delivery_channel',
            field=models.CharField(
                choices=[
                    ('profile', 'Profile only'),
                    ('email', 'Email only'),
                    ('both', 'Profile and email'),
                ],
                default='both',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='useremailpreference',
            name='event_preferences',
            field=models.JSONField(blank=True, default=_default_event_preferences),
        ),
        migrations.AddField(
            model_name='useremailpreference',
            name='notifications_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='useremailpreference',
            name='theme',
            field=models.CharField(
                choices=[('dark', 'Dark'), ('light', 'Light')],
                default='dark',
                max_length=8,
            ),
        ),
        migrations.RunPython(sync_legacy_email_preferences, migrations.RunPython.noop),
        migrations.RunPython(seed_default_templates, noop_reverse),
    ]
