from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users with password handling"""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role')


class CustomUserChangeForm(UserChangeForm):
    """Form for updating users with password handling"""
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for User model extending Django's UserAdmin
    with proper password handling and custom fields
    """
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # Campos mostrados en la vista de lista
    list_display = [
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'is_active',
        'is_staff',
        'created_at'
    ]

    # Filter options
    list_filter = [
        'role',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at'
    ]

    # Campos de búsqueda
    search_fields = [
        'username',
        'email',
        'first_name',
        'last_name',
        'phone',
        'dni'
    ]

    # Ordering
    ordering = ['-created_at']

    # Grupos de campos para editar usuarios existentes
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Personal Info', {
            'fields': (
                'first_name',
                'last_name',
                'email',
                'phone',
                'dni', 
                'address',
                'date_of_birth',
                'profile_image'
            )
        }),
        ('Role & Permissions', {
            'fields': (
                'role',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )

    # Grupos de campos para crear usuarios nuevos
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'role'
            ),
        }),
    )

    # Campos de solo lectura
    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')

    # Campos que se muestran al ver detalles de usuario
    def get_readonly_fields(self, request, obj=None):
        """Make created_at and updated_at readonly"""
        if obj:  # Editing an existing object
            return self.readonly_fields
        return []
