from django.db import migrations


OLD_DEFAULT_TEMPLATES = {
    'notification_default': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>{{message}}</p><p>Entra en {{app_name}} para revisar los detalles.</p>',
    },
    'grade_recorded': {
        'subject_template': 'Nueva calificación disponible: {{evaluation_name}}',
        'body_template': '<p>Hola {{user_name}},</p><p>Se ha registrado o actualizado tu calificación en <strong>{{subject_name}}</strong>.</p><p><strong>Evaluación:</strong> {{evaluation_name}}<br /><strong>Calificación:</strong> {{score}} / {{max_score}}</p><p>{{feedback}}</p><p>Consulta tu perfil académico en {{app_name}} para ver el detalle completo.</p>',
    },
    'message_received': {
        'subject_template': 'Nuevo mensaje de {{sender_name}}',
        'body_template': '<p>Hola {{user_name}},</p><p>Has recibido un nuevo mensaje interno.</p><p><strong>De:</strong> {{sender_name}}<br /><strong>Asunto:</strong> {{message_subject}}</p><p>{{message_preview}}</p><p>Accede a {{app_name}} para responder.</p>',
    },
    'material_added': {
        'subject_template': 'Nuevo material en {{subject_name}}',
        'body_template': '<p>Hola {{user_name}},</p><p>Se ha añadido nuevo material a tu clase de <strong>{{subject_name}}</strong>.</p><p><strong>Material:</strong> {{material_title}}<br /><strong>Publicado por:</strong> {{uploaded_by}}</p><p>Entra en {{app_name}} para consultarlo.</p>',
    },
    'admission_status': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tu solicitud en {{app_name}}.</p>',
    },
    'enrollment_status': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tu matrícula en {{app_name}}.</p>',
    },
    'document_status': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tus documentos en {{app_name}}.</p>',
    },
    'waitlist_update': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>{{message}}</p><p>Accede a {{app_name}} para actuar antes de que expire el plazo.</p>',
    },
    'email_verification': {
        'subject_template': '{{title}}',
        'body_template': '<p>Hola {{user_name}},</p><p>Activa tu cuenta de {{app_name}} desde el siguiente enlace:</p><p><a href="{{verification_url}}" class="cta">Verificar cuenta</a></p><p>Este enlace expira en 3 días.</p>',
    },
}


NEW_DEFAULT_TEMPLATES = {
    'notification_default': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>{{message}}</p><p>Entra en {{app_name}} para revisar los detalles.</p></div>',
    },
    'grade_recorded': {
        'subject_template': 'Nueva calificación disponible: {{evaluation_name}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>Se ha registrado o actualizado tu calificación en <strong>{{subject_name}}</strong>.</p><p><strong>Evaluación:</strong> {{evaluation_name}}<br /><strong>Calificación:</strong> {{score}} / {{max_score}}</p><p>{{feedback}}</p><p>Consulta tu perfil académico en {{app_name}} para ver el detalle completo.</p></div>',
    },
    'message_received': {
        'subject_template': 'Nuevo mensaje de {{sender_name}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>Has recibido un nuevo mensaje interno.</p><p><strong>De:</strong> {{sender_name}}<br /><strong>Asunto:</strong> {{message_subject}}</p><p>{{message_preview}}</p><p>Accede a {{app_name}} para responder.</p></div>',
    },
    'material_added': {
        'subject_template': 'Nuevo material en {{subject_name}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>Se ha añadido nuevo material a tu clase de <strong>{{subject_name}}</strong>.</p><p><strong>Material:</strong> {{material_title}}<br /><strong>Publicado por:</strong> {{uploaded_by}}</p><p>Entra en {{app_name}} para consultarlo.</p></div>',
    },
    'admission_status': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tu solicitud en {{app_name}}.</p></div>',
    },
    'enrollment_status': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tu matrícula en {{app_name}}.</p></div>',
    },
    'document_status': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>{{message}}</p><p>Revisa tus documentos en {{app_name}}.</p></div>',
    },
    'waitlist_update': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>{{message}}</p><p>Accede a {{app_name}} para actuar antes de que expire el plazo.</p></div>',
    },
    'email_verification': {
        'subject_template': '{{title}}',
        'body_template': '<div class="section"><p>Hola {{user_name}},</p><p>Activa tu cuenta de {{app_name}} desde el siguiente enlace:</p><p><a href="{{verification_url}}" class="cta">Verificar cuenta</a></p><p>Este enlace expira en 3 días.</p></div>',
    },
}


def migrate_default_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('notifications', 'EmailTemplate')
    for name, new_values in NEW_DEFAULT_TEMPLATES.items():
        current = EmailTemplate.objects.filter(name=name).first()
        if current is None:
            EmailTemplate.objects.create(name=name, **new_values, description='Plantilla del sistema actualizada con diseño de marca.', is_active=True)
            continue

        old_values = OLD_DEFAULT_TEMPLATES[name]
        if current.subject_template == old_values['subject_template'] and current.body_template == old_values['body_template']:
            current.subject_template = new_values['subject_template']
            current.body_template = new_values['body_template']
            current.save(update_fields=['subject_template', 'body_template', 'updated_at'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0010_systemsettings_admission_waitlist_grace_days'),
    ]

    operations = [
        migrations.RunPython(migrate_default_templates, noop_reverse),
    ]
