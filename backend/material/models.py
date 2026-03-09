from django.db import models
from django.conf import settings


class Material(models.Model):
    TYPE_CHOICES = [
        ('document', 'Document'),
        ('video', 'Video'),
        ('link', 'Link'),
        ('other', 'Other'),
    ]
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    cls = models.ForeignKey('academic.Class', on_delete=models.CASCADE, related_name='materials')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='materials'
    )
    file = models.FileField(upload_to='materials/', null=True, blank=True)
    url = models.URLField(blank=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='document')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
