from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with all fields.
    Used for retrieving user information.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

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
            'phone',
            'address',
            'date_of_birth',
            'profile_image',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with password validation.
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
        label='Confirm Password'
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'password2',
            'first_name',
            'last_name',
            'role',
            'phone',
            'address',
            'date_of_birth',
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs

    def validate_email(self, value):
        """Validate that email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        """Create user with encrypted password"""
        # Remove password2 as it's not needed for user creation
        validated_data.pop('password2')

        # Create user with create_user method to properly hash password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 's'),
            phone=validated_data.get('phone', ''),
            address=validated_data.get('address', ''),
            date_of_birth=validated_data.get('date_of_birth', None),
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile.
    Password updates are handled separately.
    """
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address',
            'date_of_birth',
            'profile_image',
        ]

    def validate_email(self, value):
        """Validate that email is unique (excluding current user)"""
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


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
    Serializer for the teacher list endpoint.
    Includes annotated active_classes_count field.
    """
    active_classes_count = serializers.IntegerField(default=0)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'active_classes_count']


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
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
        label='Confirm New Password'
    )

    def validate(self, attrs):
        """Validate that new passwords match"""
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs

    def validate_old_password(self, value):
        """Validate that old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value

    def save(self, **kwargs):
        """Update user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
