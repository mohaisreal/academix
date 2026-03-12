from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.db.models import Avg, Count, OuterRef, Q, Subquery
from enrollment.models import CareerEnrollment
from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    StudentListSerializer,
    TeacherListSerializer,
)


class IsManagementOrAdmin(permissions.BasePermission):
    """Allow access only to users with role 'm' (management) or 'a' (administration)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['m', 'a']


class IsManagementAdminOrTeacher(permissions.BasePermission):
    """Allow access only to users with role 'm', 'a', or 't'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['m', 'a', 't']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer to include user data in the token response
    """
    def validate(self, attrs):
        data = super().validate(attrs)

        # Add custom claims
        data['user'] = UserSerializer(self.user).data

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view to return user data along with tokens
    """
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    POST /api/users/register/
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens for the new user
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'User registered successfully.'
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """
    API endpoint for user login with JWT tokens.
    POST /api/users/login/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({
                'error': 'Please provide both username and password.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if not user:
            return Response({
                'error': 'Invalid credentials.'
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({
                'error': 'Account is disabled.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Login successful.'
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    API endpoint for user logout (blacklist refresh token).
    POST /api/users/logout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response({
                    'error': 'Refresh token is required.'
                }, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({
                'message': 'Logout successful.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Invalid token or token already blacklisted.'
            }, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    API endpoint to get and update current authenticated user.
    GET /api/users/me/
    PUT/PATCH /api/users/me/
    """
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        """Get current user details"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(generics.UpdateAPIView):
    """
    API endpoint for changing user password.
    POST /api/users/change-password/
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """
    API endpoint to list all users (admin only).
    GET /api/users/
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for user detail, update, and delete (admin or owner only).
    GET /api/users/<id>/
    PUT/PATCH /api/users/<id>/
    DELETE /api/users/<id>/
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        """
        Admin can access all users, regular users can only access themselves
        """
        if self.request.method == 'DELETE':
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def check_object_permissions(self, request, obj):
        """
        Check if user has permission to access this object
        """
        super().check_object_permissions(request, obj)

        # Allow admin or the user themselves
        if not request.user.is_staff and obj != request.user:
            self.permission_denied(
                request,
                message='You do not have permission to access this user.'
            )


class StudentListView(generics.ListAPIView):
    """
    API endpoint to list all students with career and GPA data.
    GET /api/users/students/
    Accessible by management, administration, and teachers.
    """
    serializer_class = StudentListSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagementAdminOrTeacher]

    def get_queryset(self):
        latest_career_id = CareerEnrollment.objects.filter(
            student=OuterRef('pk'), status='active'
        ).order_by('-enrolled_at').values('career__id')[:1]

        latest_career_name = CareerEnrollment.objects.filter(
            student=OuterRef('pk'), status='active'
        ).order_by('-enrolled_at').values('career__name')[:1]

        return User.objects.filter(role='s').annotate(
            career_id_ann=Subquery(latest_career_id),
            career_name_ann=Subquery(latest_career_name),
            gpa=Avg('grades__score'),
        )


class TeacherListView(generics.ListAPIView):
    """
    API endpoint to list all teachers with their active class count.
    GET /api/users/teachers/
    Accessible by management and administration only.
    """
    serializer_class = TeacherListSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagementOrAdmin]

    def get_queryset(self):
        return User.objects.filter(role='t').annotate(
            active_classes_count=Count(
                'teaching_classes',
                filter=Q(teaching_classes__period__is_active=True)
            )
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def health_check(request):
    """
    Simple health check endpoint to verify API is working.
    GET /api/health/
    """
    return Response({
        'status': 'healthy',
        'user': request.user.username,
        'message': 'API is running successfully.'
    })
