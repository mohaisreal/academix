import logging
import re

from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags

from .models import (
    Notification,
    SystemSettings,
    UserEmailPreference,
    EmailTemplate,
    NOTIFICATION_DELIVERY_BOTH,
    NOTIFICATION_DELIVERY_EMAIL,
    NOTIFICATION_DELIVERY_PROFILE,
    NOTIFICATION_EVENT_ALIASES,
    NOTIFICATION_EVENT_DEFINITIONS,
    default_event_preferences,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades de renderizado de plantillas
# ---------------------------------------------------------------------------

def render_template(template_str, context):
    """
    Sustituye los patrones ``{{placeholder}}`` de *template_str* por valores de
    *context*. Los marcadores desconocidos se dejan tal cual para que las claves ausentes no generen en silencio una salida rota difícil de depurar.

    Marcadores integrados siempre disponibles (los llamadores pueden sobrescribirlos
    incluyendo las mismas claves en *context*):
        - ``{{app_name}}``   → "Academix"

    Los llamadores deben inyectar ``{{user_name}}`` y ``{{user_email}}`` por su cuenta,
    ya que esta función es deliberadamente independiente del usuario.
    """
    resolved = {'app_name': 'Academix'}
    resolved.update(context)

    def replacer(match):
        key = match.group(1).strip()
        return str(resolved.get(key, match.group(0)))

    return re.sub(r'\{\{([^}]+)\}\}', replacer, template_str)


def wrap_in_email_layout(html_body, system_settings):
    """
    Envuelve *html_body* (que puede contener etiquetas ``<img>`` y HTML arbitrario)
    en una estructura de correo con estilo y adaptable que usa:
        - ``system_settings.email_header_color``
        - ``system_settings.email_logo_url``
        - ``system_settings.email_footer_text``
    """
    header_color = system_settings.email_header_color or '#4F46E5'
    footer_text = system_settings.email_footer_text or 'Academix'

    logo_html = ''
    if system_settings.email_logo_url:
        logo_html = (
            f'<img src="{system_settings.email_logo_url}" '
            f'alt="Academix" style="max-height:48px;display:block;" />'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body {{ margin: 0; padding: 0; background-color: #f4f4f5; font-family: Arial, sans-serif; }}
    .wrapper {{ max-width: 600px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
    .header {{ background-color: {header_color}; padding: 24px 32px; }}
    .body {{ padding: 32px; color: #111827; font-size: 15px; line-height: 1.6; }}
    .body img {{ max-width: 100%; height: auto; }}
    .footer {{ background-color: #f9fafb; border-top: 1px solid #e5e7eb; padding: 16px 32px; font-size: 12px; color: #6b7280; text-align: center; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">{logo_html}</div>
    <div class="body">{html_body}</div>
    <div class="footer">{footer_text}</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Creación de notificaciones
# ---------------------------------------------------------------------------


EVENT_TEMPLATE_MAP = {
    item['key']: item['template_name']
    for item in NOTIFICATION_EVENT_DEFINITIONS
}
EVENT_TEMPLATE_MAP['email_verification'] = 'email_verification'


def canonical_event_type(event_type):
    if not event_type:
        return ''
    return NOTIFICATION_EVENT_ALIASES.get(event_type, event_type)


def user_allows_event(preference, event_type):
    canonical = canonical_event_type(event_type)
    if not canonical:
        return True
    defaults = default_event_preferences()
    if canonical not in defaults:
        return True
    merged = defaults
    merged.update(preference.event_preferences or {})
    return bool(merged.get(canonical, True))


def resolve_email_template(template_name=None, event_type=None):
    """
    Resolve the active administrator-managed template for a notification.

    Priority:
      1. Explicit template_name from caller.
      2. Template mapped from the canonical event type.
      3. Active notification_default fallback for unknown/generic events only.

    If none is active/registered, the email is intentionally not sent. That is
    better than silently bypassing the administrator-controlled template system.
    """
    canonical = canonical_event_type(event_type)
    if template_name:
        return EmailTemplate.objects.filter(name=template_name, is_active=True).first()

    mapped = EVENT_TEMPLATE_MAP.get(canonical)
    if mapped:
        return EmailTemplate.objects.filter(name=mapped, is_active=True).first()

    return EmailTemplate.objects.filter(name='notification_default', is_active=True).first()


def create_notification(
    user,
    title,
    message,
    notif_type='info',
    event_type=None,
    template_name=None,
    send_email=True,
    context=None,
):
    """
    Creates a profile Notification and/or sends an email according to the
    user's notification preferences.

    Args:
        user: The target user.
        title: Notification title and default email subject.
        message: Plain-text notification body.
        notif_type: One of 'info', 'success', 'warning', 'error'.
        event_type: Optional free-text event classifier stored on the record.
        template_name: Optional EmailTemplate.name.  When provided and the
            template is active, the email is sent as HTML using the rendered
            template.  The subject comes from the template's subject_template.
            Context automatically includes ``user_name``, ``user_email``, and
            ``app_name``; the plain *message* and *title* are also injected as
            ``{{message}}`` and ``{{title}}`` so templates can embed them.
        context: Optional dict with event-specific template values.
    """
    user_pref, _ = UserEmailPreference.objects.get_or_create(user=user)
    if not user_pref.notifications_enabled:
        return None

    if not user_allows_event(user_pref, event_type):
        return None

    wants_profile = user_pref.delivery_channel in (
        NOTIFICATION_DELIVERY_PROFILE,
        NOTIFICATION_DELIVERY_BOTH,
    )
    wants_email = user_pref.delivery_channel in (
        NOTIFICATION_DELIVERY_EMAIL,
        NOTIFICATION_DELIVERY_BOTH,
    )

    notif = None
    if wants_profile:
        notif = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            type=notif_type,
            event_type=event_type or '',
        )

    if not send_email or not wants_email or not user.email:
        return notif

    system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
    if not system_settings.email_notifications_enabled:
        return notif

    if not user_pref.email_enabled:
        return notif

    # Construye el contexto base disponible para todas las plantillas
    base_context = {
        'user_name': getattr(user, 'get_full_name', lambda: user.username)() or user.username,
        'user_email': user.email,
        'app_name': 'Academix',
        'message': message,
        'title': title,
    }
    if context:
        base_context.update(context)

    template = resolve_email_template(template_name=template_name, event_type=event_type)
    if template is None:
        logger.warning(
            'Email not sent to %s: no active template found for event_type=%s template_name=%s',
            user.email,
            event_type,
            template_name,
        )
        return notif

    email_subject = render_template(template.subject_template, base_context)
    rendered_body = render_template(template.body_template, base_context)
    html_message = wrap_in_email_layout(rendered_body, system_settings)
    plain_text = strip_tags(rendered_body).strip() or message

    try:
        send_mail(
            subject=email_subject,
            message=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send email to %s', user.email)

    return notif
