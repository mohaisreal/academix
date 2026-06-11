from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

# Crea aquí tus modelos.

class User(AbstractUser):
    """
    Extended base user model from AbstractUser with additional fields
    for role-based access and profile information.
    """
    ROLE_CHOICES = [
        ('s', 'student'),
        ('t', 'teacher'),
        ('m', 'management'),
        ('a', 'administration')
    ]
    IDENTITY_STATUS_CHOICES = [
        ('unsubmitted', 'Unsubmitted'),
        ('pending', 'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    # Teléfono number validator - allows international format
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Teléfono number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    role = models.CharField(max_length=1, choices=ROLE_CHOICES, default='s')
    dni = models.CharField(max_length=20, unique=True, blank=True, null=True)
    email_verified = models.BooleanField(default=True)
    identity_verification_status = models.CharField(
        max_length=20,
        choices=IDENTITY_STATUS_CHOICES,
        default='approved',
    )
    identity_verification_notes = models.TextField(blank=True, null=True)
    identity_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='identity_reviews_performed',
    )
    identity_reviewed_at = models.DateTimeField(blank=True, null=True)
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        help_text="Teléfono number in international format"
    )
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.username

    @property
    def can_access_platform(self):
        """
        Publicly registered students must pass email and identity verification.
        Staff/admin-created accounts remain controlled by is_active and role.
        """
        if self.role != 's':
            return self.is_active
        return (
            self.is_active
            and self.email_verified
            and self.identity_verification_status == 'approved'
        )


class IdentityVerificationDocument(models.Model):
    """
    Proof document uploaded by a newly registered student after email verification.
    Gestión reviews the user as a whole, not each file independently.
    """
    DOCUMENT_TYPE_CHOICES = [
        ('identity', 'Identity document'),
        ('supporting', 'Supporting evidence'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='identity_documents',
    )
    file = models.FileField(upload_to='identity_verifications/')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default='identity')
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Identity verification document'
        verbose_name_plural = 'Identity verification documents'

    def __str__(self):
        return self.original_filename or self.file.name
