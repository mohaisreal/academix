import os
import random
import re
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from academic.models import Department
from .models import IdentityVerificationDocument, User


def _generate_student_id(fmt: str) -> str:
    """
    Genera una cadena de ID de estudiante a partir de un patrón de formato simple.

    Tokens soportados:
      \\d{N}    → N dígitos decimales aleatorios
      [A-Z]{N} → N letras ASCII mayúsculas aleatorias

    Todo lo demás se trata como prefijo/sufijo literal.
    Formatos de ejemplo:
      \\d{6}         → "483920"
      STU-\\d{6}    → "STU-483920"
      [A-Z]{2}\\d{4} → "KJ7823"
    """
    result = fmt
    # Reemplaza \d{N}
    for m in re.finditer(r'\\d\{(\d+)\}', fmt):
        n = int(m.group(1))
        digits = ''.join(random.choices('0123456789', k=n))
        result = result.replace(m.group(0), digits, 1)
    # Reemplaza [A-Z]{N}
    for m in re.finditer(r'\[A-Z\]\{(\d+)\}', result):
        n = int(m.group(1))
        letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=n))
        result = result.replace(m.group(0), letters, 1)
    return result


def _unique_student_id(fmt: str) -> str:
    """Sigue generando hasta que el nombre de usuario sea único."""
    for _ in range(50):
        candidate = _generate_student_id(fmt)
        if not User.objects.filter(username=candidate).exists():
            return candidate
    # Respaldo: añade dígitos aleatorios adicionales para garantizar unicidad
    return _generate_student_id(fmt) + str(random.randint(100, 999))


class UserSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Usuario con todos los campos.
    Se usa para recuperar información del usuario.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    identity_verification_status_display = serializers.CharField(
        source='get_identity_verification_status_display',
        read_only=True,
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'role',
            'role_display',
            'department',
            'department_name',
            'dni',
            'email_verified',
            'identity_verification_status',
            'identity_verification_status_display',
            'identity_verification_notes',
            'phone',
            'address',
            'date_of_birth',
            'profile_image',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'email_verified',
            'identity_verification_status',
            'identity_verification_status_display',
            'identity_verification_notes',
            'created_at',
            'updated_at',
        ]


class IdentityVerificationDocumentSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = IdentityVerificationDocument
        fields = [
            'id',
            'file_name',
            'download_url',
            'document_type',
            'original_filename',
            'uploaded_at',
        ]
        read_only_fields = ['id', 'file_name', 'download_url', 'original_filename', 'uploaded_at']

    def get_file_name(self, obj):
        if not obj.file:
            return None
        return obj.original_filename or os.path.basename(obj.file.name)

    def get_download_url(self, obj):
        return f"/users/identity-verification-documents/{obj.id}/download/"


class IdentityVerificationUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    identity_verification_status_display = serializers.CharField(
        source='get_identity_verification_status_display',
        read_only=True,
    )
    identity_documents = IdentityVerificationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'role',
            'role_display',
            'dni',
            'email_verified',
            'identity_verification_status',
            'identity_verification_status_display',
            'identity_verification_notes',
            'identity_reviewed_at',
            'is_active',
            'created_at',
            'identity_documents',
        ]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializador para registro de usuarios con validación de contraseña.
    El nombre de usuario se genera automáticamente a partir de la configuración student_id_format del sistema.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label='Confirmar contraseña'
    )

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'password2',
            'first_name',
            'last_name',
            'role',
            'dni',
            'phone',
            'address',
            'date_of_birth',
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'dni': {'required': False, 'allow_blank': True, 'allow_null': True},
        }

    def validate(self, attrs):
        """Valida que las contraseñas coincidan."""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Datos de inicio de sesión incorrectos."
            })
        return attrs

    def validate_email(self, value):
        """Valida que el correo electrónico sea único."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        """Crea un usuario. El ID de estudiante (username) se asigna en la primera matrícula."""
        validated_data.pop('password2')

        # Usa el correo como nombre de usuario temporal hasta que la primera matrícula asigne un ID permanente de estudiante.
        username = validated_data['email']

        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 's'),
            dni=validated_data.get('dni', None),
            phone=validated_data.get('phone', ''),
            address=validated_data.get('address', ''),
            date_of_birth=validated_data.get('date_of_birth', None),
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializador para actualizar el perfil de usuario.
    Las actualizaciones de contraseña se manejan por separado.
    """
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'dni',
            'phone',
            'address',
            'date_of_birth',
            'profile_image',
        ]

    def validate_email(self, value):
        """Valida que el correo electrónico sea único (excluyendo al usuario actual)."""
        instance = getattr(self, 'instance', None)
        qs = User.objects.filter(email=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class AdminUserWriteSerializer(serializers.ModelSerializer):
    """
    Serializador para creación de usuarios de gestión/admin y actualizaciones administrativas.
    Está intencionalmente separado de UserUpdateSerializer para que las actualizaciones
    de perfil regulares no modifiquen silenciosamente rol, estado activo o contraseña.
    """
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'department',
            'department_name',
            'dni',
            'phone',
            'address',
            'date_of_birth',
            'is_active',
            'email_verified',
            'identity_verification_status',
            'identity_verification_notes',
            'password',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'username': {'required': True},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'dni': {'required': False, 'allow_blank': True, 'allow_null': True},
            'phone': {'required': False, 'allow_blank': True, 'allow_null': True},
            'address': {'required': False, 'allow_blank': True, 'allow_null': True},
            'date_of_birth': {'required': False, 'allow_null': True},
            'is_active': {'required': False},
        }

    def validate_username(self, value):
        qs = User.objects.filter(username=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        qs = User.objects.filter(email=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Contraseña is required when creating a user.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        department = validated_data.pop('department', None)
        if validated_data.get('role') != 't':
            department = None
        user = User.objects.create_user(password=password, **validated_data)
        if department is not None:
            user.department = department
            user.save(update_fields=['department'])
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        department = validated_data.pop('department', serializers.empty)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if instance.role != 't':
            instance.department = None
        elif department is not serializers.empty:
            instance.department = department
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class StudentListSerializer(serializers.ModelSerializer):
    """
    Serializer for the student list endpoint.
    Includes annotated career and GPA fields.
    """
    career_id = serializers.IntegerField(source='career_id_ann', default=None)
    career_name = serializers.CharField(source='career_name_ann', default=None)
    gpa = serializers.DecimalField(max_digits=6, decimal_places=2, default=None)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'career_id', 'career_name', 'gpa']


class TeacherListSerializer(serializers.ModelSerializer):
    """
    Serializador para el endpoint de listado de docentes.
    Incluye el campo anotado active_classes_count.
    """
    active_classes_count = serializers.IntegerField(default=0)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'active_classes_count']


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializador para el endpoint de cambio de contraseña.
    """
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        label='Confirmar nueva contraseña'
    )

    def validate(self, attrs):
        """Valida que las nuevas contraseñas coincidan."""
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "Datos de inicio de sesión incorrectos."
            })
        return attrs

    def validate_old_password(self, value):
        """Valida que la contraseña anterior sea correcta."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña antigua incorrecta.")
        return value

    def save(self, **kwargs):
        """Actualiza la contraseña del usuario"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
