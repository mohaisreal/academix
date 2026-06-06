from django.db import migrations


CHAT_TEMPLATE = {
    'subject_template': 'Nuevo mensaje de {{sender_name}}',
    'body_template': (
        '<div class="section"><p>Hola {{user_name}},</p>'
        '<p>Has recibido un nuevo mensaje en Academix.</p>'
        '<p><strong>De:</strong> {{sender_name}}<br />'
        '<strong>Asunto:</strong> {{message_subject}}</p>'
        '<p>{{message_preview}}</p>'
        '<p>Accede a {{app_name}} para responder.</p></div>'
    ),
    'description': 'Plantilla dedicada para avisos de nuevos mensajes de chat.',
    'is_active': True,
}


def create_chat_message_template(apps, schema_editor):
    EmailTemplate = apps.get_model('notifications', 'EmailTemplate')
    template, created = EmailTemplate.objects.get_or_create(
        name='chat_message_received',
        defaults=CHAT_TEMPLATE,
    )
    if not created and not template.subject_template and not template.body_template:
        template.subject_template = CHAT_TEMPLATE['subject_template']
        template.body_template = CHAT_TEMPLATE['body_template']
        template.description = CHAT_TEMPLATE['description']
        template.is_active = True
        template.save(update_fields=['subject_template', 'body_template', 'description', 'is_active', 'updated_at'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0011_branded_default_email_templates'),
    ]

    operations = [
        migrations.RunPython(create_chat_message_template, noop_reverse),
    ]
