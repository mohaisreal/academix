from django.contrib import admin
from .models import EmailTemplate, Notification, SystemSettings, UserEmailPreference


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Notificaciones', {
            'fields': (
                'email_notifications_enabled',
                'email_header_color',
                'email_logo_url',
                'email_footer_text',
            ),
        }),
        ('Identificación y admisiones', {
            'fields': (
                'student_id_format',
                'admission_public_dni_mask_regex',
                'admission_public_dni_mask_replacement',
            ),
        }),
        ('Cobros de matrícula', {
            'fields': (
                'school_insurance_fee',
                'transcript_opening_fee',
                'enrollment_extra_charges',
            ),
        }),
    )


admin.site.register(Notification)
admin.site.register(UserEmailPreference)
admin.site.register(EmailTemplate)
