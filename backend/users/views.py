from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import FileResponse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings as django_settings
from django.utils.text import get_valid_filename
from django.db.models import Avg, Count, OuterRef, Q, Subquery
import mimetypes
from admissions.permissions import IsManagement
from enrollment.models import CareerEnrollment
from .models import IdentityVerificationDocument, User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    AdminUserWriteSerializer,
    ChangePasswordSerializer,
    StudentListSerializer,
    TeacherListSerializer,
    IdentityVerificationUserSerializer,
    IdentityVerificationDocumentSerializer,
)


class IsManagementOrAdmin(permissions.BasePermission):
    """Permite acceso solo a usuarios con rol 'm' (gestión) o 'a' (administración)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['m', 'a']


class IsManagementAdminOrTeacher(permissions.BasePermission):
    """Permite acceso solo a usuarios con rol 'm', 'a' o 't'."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['m', 'a', 't']


def _resolve_user_from_email_token(uid, token):
    """Resuelve y valida el mismo token firmado usado por el enlace de verificación de correo."""
    if not uid or not token:
        return None
    try:
        user_pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None

    token_generator = PasswordResetTokenGenerator()
    if not token_generator.check_token(user, token):
        return None
    return user


def _student_access_denial(user):
    """
    Devuelve un motivo visible para el usuario cuando un estudiante aún no puede acceder a la plataforma.
    Es intencionalmente explícito: una barrera de seguridad debe indicar qué falta.
    """
    if user.role != 's':
        return None
    if not user.email_verified:
        return 'Tienes que verificar tu correo electrónico antes de iniciar sesión.'
    if user.identity_verification_status == 'unsubmitted':
        return 'Tu correo electrónico está verificado, pero todavía tienes que subir las pruebas de identidad.'
    if user.identity_verification_status == 'pending':
        return 'Tus pruebas de identidad están pendientes de revisión por Gestión.'
    if user.identity_verification_status == 'rejected':
        return 'Gestión rechazó la verificación de identidad. Sube documentación corregida o contacta con soporte.'
    if user.identity_verification_status != 'approved':
        return 'Tu cuenta todavía no está autorizada por Gestión.'
    if not user.is_active:
        return 'Tu cuenta todavía no está activa.'
    return None


def _send_email_verification(user):
    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verify_url = f"{django_settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    from notifications.utils import create_notification
    create_notification(
        user=user,
        title='Verifica tu cuenta en Academix',
        message=f'Hola {user.first_name},\n\nVerifica tu correo electrónico con este enlace:\n{verify_url}\n\nDespués tendrás que subir pruebas de identidad para que Gestión autorice tu cuenta.',
        notif_type='info',
        event_type='email_verification',
        template_name='email_verification',
        context={'verification_url': verify_url},
    )
    return verify_url


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializador JWT personalizado para incluir datos del usuario en la respuesta del token
    """
    def validate(self, attrs):
        identifier = attrs.get(self.username_field)
        password = attrs.get('password')
        if identifier and password:
            candidate = User.objects.filter(
                Q(username=identifier) | Q(email=identifier)
            ).first()
            if candidate and candidate.check_password(password):
                denial = _student_access_denial(candidate)
                if denial:
                    from rest_framework_simplejwt.exceptions import AuthenticationFailed
                    raise AuthenticationFailed(denial, code='account_not_ready')

        data = super().validate(attrs)

        denial = _student_access_denial(self.user)
        if denial:
            from rest_framework_simplejwt.exceptions import AuthenticationFailed
            raise AuthenticationFailed(denial, code='account_not_ready')

        # Agrega claims personalizados
        data['user'] = UserSerializer(self.user).data

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Vista JWT personalizada para devolver datos del usuario junto con los tokens
    """
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """
    Endpoint de API para registro de usuarios.
    POST /api/users/register/
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.role = 's'
        user.is_active = False
        user.email_verified = False
        user.identity_verification_status = 'unsubmitted'
        user.identity_verification_notes = ''
        user.identity_reviewed_by = None
        user.identity_reviewed_at = None
        user.save(update_fields=[
            'role',
            'is_active',
            'email_verified',
            'identity_verification_status',
            'identity_verification_notes',
            'identity_reviewed_by',
            'identity_reviewed_at',
        ])
        _send_email_verification(user)

        return Response({
            'user': UserSerializer(user).data,
            'message': 'Registro exitoso. Revisa tu correo electrónico; después Gestión deberá validar tu identidad.'
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """
    Endpoint de API para inicio de sesión de usuarios con tokens JWT.
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

        user = User.objects.filter(Q(username=username) | Q(email=username)).first()

        if not user or not user.check_password(password):
            return Response({
                'error': 'Credenciales inválidas.'
            }, status=status.HTTP_401_UNAUTHORIZED)

        denial = _student_access_denial(user)
        if denial:
            return Response({
                'error': denial,
                'identity_verification_status': user.identity_verification_status,
                'email_verified': user.email_verified,
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.is_active:
            return Response({
                'error': 'Account is disabled.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Genera tokens JWT
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Inicio de sesión exitoso.'
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    Endpoint de API para cierre de sesión de usuarios (lista negra del refresh token).
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
                'message': 'Cierre de sesión exitoso.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Token inválido o ya bloqueado.'
            }, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Endpoint de API para obtener y actualizar el usuario autenticado actual.
    GET /api/users/me/
    PUT/PATCH /api/users/me/
    """
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        """Obtiene los detalles del usuario actual."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(generics.UpdateAPIView):
    """
    Endpoint de API para cambiar la contraseña del usuario.
    POST /api/users/change-password/
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Contraseña changed exitosaly.'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListCreateAPIView):
    """
    Endpoint de API para listar/crear usuarios (solo gestión / administración).
    GET  /api/users/
    POST /api/users/
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsManagement]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminUserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
            )

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint de API para detalle, actualización y eliminación de usuarios (solo admin o propietario).
    GET /api/users/<id>/
    PUT/PATCH /api/users/<id>/
    DELETE /api/users/<id>/
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            if self.request.user.role in ('m', 'a'):
                return AdminUserWriteSerializer
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        """
        Gestión/admin puede acceder a todos los usuarios; los usuarios regulares solo pueden acceder a sí mismos.
        """
        if self.request.method == 'DELETE':
            return [IsManagement()]
        return [permissions.IsAuthenticated()]

    def check_object_permissions(self, request, obj):
        """
        Verifica si el usuario tiene permiso para acceder a este objeto.
        """
        super().check_object_permissions(request, obj)

        # Permite gestión/administración o el propio usuario
        if request.user.role not in ('m', 'a') and obj != request.user:
            self.permission_denied(
                request,
                message='You do not have permission to access this user.'
            )


class StudentListView(generics.ListAPIView):
    """
    Endpoint de API para listar todos los estudiantes con datos de carrera y GPA.
    GET /api/users/students/
    Accesible por gestión, administración y docentes.
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
        'message': 'API is running exitosaly.'
    })


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Registro de estudiante con verificación de email.
    """
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Crear usuario inactivo
        user = serializer.save()
        user.role = 's'
        user.is_active = False
        user.email_verified = False
        user.identity_verification_status = 'unsubmitted'
        user.identity_verification_notes = ''
        user.identity_reviewed_by = None
        user.identity_reviewed_at = None
        user.save(update_fields=[
            'role',
            'is_active',
            'email_verified',
            'identity_verification_status',
            'identity_verification_notes',
            'identity_reviewed_by',
            'identity_reviewed_at',
        ])

        _send_email_verification(user)

        return Response(
            {"detail": "Registro exitoso. Revisa tu correo electrónico y después sube las pruebas de identidad para que Gestión autorice tu cuenta."},
            status=status.HTTP_201_CREATED
        )


class VerifyEmailView(generics.GenericAPIView):
    """
    GET /api/auth/verify-email/?uid=<uid_b64>&token=<token>
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        uid = request.query_params.get('uid')
        token = request.query_params.get('token')

        user = _resolve_user_from_email_token(uid, token)
        if not user:
            return Response({"detail": "Enlace inválido o expirado."}, status=status.HTTP_400_BAD_REQUEST)

        update_fields = []
        if not user.email_verified:
            user.email_verified = True
            update_fields.append('email_verified')
        if update_fields:
            user.save(update_fields=update_fields)

        return Response({
            "detail": "Email verificado correctamente. Ahora sube las pruebas de identidad para revisión de Gestión.",
            "requires_identity_verification": user.role == 's' and user.identity_verification_status != 'approved',
            "identity_verification_status": user.identity_verification_status,
        }, status=status.HTTP_200_OK)


class IdentityDocumentUploadView(APIView):
    """
    POST /api/auth/identity-documents/?uid=<uid_b64>&token=<token>
    Upload identity proof files after email verification, before the account is active.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uid = request.query_params.get('uid')
        token = request.query_params.get('token')
        user = _resolve_user_from_email_token(uid, token)
        if not user:
            return Response({"detail": "Enlace inválido o expirado."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.email_verified:
            return Response({"detail": "Primero tienes que verificar el correo electrónico."}, status=status.HTTP_400_BAD_REQUEST)
        if user.role != 's':
            return Response({"detail": "Este flujo solo aplica a estudiantes."}, status=status.HTTP_400_BAD_REQUEST)
        if user.identity_verification_status == 'approved' and user.is_active:
            return Response({"detail": "La cuenta ya está autorizada."}, status=status.HTTP_400_BAD_REQUEST)

        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files and request.FILES.get('file'):
            files = [request.FILES['file']]
        if not files:
            return Response({"detail": "Sube al menos un fichero de prueba de identidad."}, status=status.HTTP_400_BAD_REQUEST)

        document_type = request.data.get('document_type', 'identity')
        valid_document_types = {choice[0] for choice in IdentityVerificationDocument.DOCUMENT_TYPE_CHOICES}
        if document_type not in valid_document_types:
            return Response({"detail": "Tipo de documento inválido."}, status=status.HTTP_400_BAD_REQUEST)

        documents = []
        for uploaded in files:
            documents.append(IdentityVerificationDocument.objects.create(
                user=user,
                file=uploaded,
                original_filename=getattr(uploaded, 'name', ''),
                document_type=document_type,
            ))

        user.identity_verification_status = 'pending'
        user.identity_verification_notes = ''
        user.identity_reviewed_by = None
        user.identity_reviewed_at = None
        user.is_active = False
        user.save(update_fields=[
            'identity_verification_status',
            'identity_verification_notes',
            'identity_reviewed_by',
            'identity_reviewed_at',
            'is_active',
            'updated_at',
        ])

        return Response({
            "detail": "Pruebas recibidas. Gestión debe revisar y autorizar la cuenta antes de que puedas entrar.",
            "identity_verification_status": user.identity_verification_status,
            "documents": IdentityVerificationDocumentSerializer(documents, many=True).data,
        }, status=status.HTTP_201_CREATED)


class IdentityVerificationListView(generics.ListAPIView):
    """
    GET /api/users/identity-verifications/?status=pending
    Gestión queue for student identity checks.
    """
    serializer_class = IdentityVerificationUserSerializer
    permission_classes = [IsManagement]

    def get_queryset(self):
        status_filter = self.request.query_params.get('status', 'pending')
        qs = User.objects.filter(role='s').prefetch_related('identity_documents').order_by('created_at')
        if status_filter and status_filter != 'all':
            qs = qs.filter(identity_verification_status=status_filter)
        return qs


class IdentityVerificationReviewView(APIView):
    """
    POST /api/users/identity-verifications/<user_id>/review/
    Body: {"status": "approved|rejected", "notes": "..."}
    """
    permission_classes = [IsManagement]

    def post(self, request, user_id):
        decision = request.data.get('status')
        notes = request.data.get('notes', '')
        if decision not in ('approved', 'rejected'):
            return Response({"detail": "status debe ser 'approved' o 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_id, role='s')
        except User.DoesNotExist:
            return Response({"detail": "Estudiante no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if not user.email_verified:
            return Response({"detail": "No se puede revisar una cuenta sin email verificado."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.identity_documents.exists():
            return Response({"detail": "No hay documentos de identidad para revisar."}, status=status.HTTP_400_BAD_REQUEST)

        user.identity_verification_status = decision
        user.identity_verification_notes = notes
        user.identity_reviewed_by = request.user
        user.identity_reviewed_at = timezone.now()
        user.is_active = decision == 'approved'
        user.save(update_fields=[
            'identity_verification_status',
            'identity_verification_notes',
            'identity_reviewed_by',
            'identity_reviewed_at',
            'is_active',
            'updated_at',
        ])

        from notifications.utils import create_notification
        if decision == 'approved':
            create_notification(
                user=user,
                title='Cuenta autorizada',
                message='Gestión ha verificado tu identidad. Ya puedes iniciar sesión en Academix.',
                notif_type='success',
                event_type='identity_verification_approved',
            )
        else:
            create_notification(
                user=user,
                title='Verificación de identidad rechazada',
                message=notes or 'Gestión necesita documentación corregida antes de autorizar tu cuenta.',
                notif_type='warning',
                event_type='identity_verification_rejected',
            )

        return Response(IdentityVerificationUserSerializer(user).data, status=status.HTTP_200_OK)


class IdentityVerificationDocumentDownloadView(APIView):
    permission_classes = [IsManagement]

    def get(self, request, document_id):
        try:
            document = IdentityVerificationDocument.objects.get(pk=document_id)
        except IdentityVerificationDocument.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not document.file:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            file_handle = document.file.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        content_type, encoding = mimetypes.guess_type(document.file.name)
        filename = get_valid_filename(document.original_filename or document.file.name.rsplit('/', 1)[-1])
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=filename,
            content_type=content_type or 'application/octet-stream',
        )
        if encoding:
            response.headers['Content-Encoding'] = encoding
        return response
