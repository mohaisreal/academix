from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'questionnaires', views.QuestionnaireViewSet, basename='questionnaire')

urlpatterns = [
    path('', include(router.urls)),

    # Export / Import
    path('questionnaires/<int:pk>/export/', views.QuestionnaireExportView.as_view(), name='questionnaire-export'),
    path('import/', views.QuestionnaireImportView.as_view(), name='questionnaire-import'),

    # Estudiante: iniciar/gestionar respuestas
    path('questionnaires/<int:pk>/start/', views.StartResponseView.as_view(), name='questionnaire-start'),
    path('responses/<int:pk>/', views.ResponseDetailView.as_view(), name='response-detail'),
    path('responses/<int:pk>/submit/', views.SubmitResponseView.as_view(), name='response-submit'),
    path('responses/<int:pk>/answers/', views.BulkAnswerView.as_view(), name='response-answers'),
    path(
        'responses/<int:response_pk>/questions/<int:question_pk>/payment-intent/',
        views.CreateResponseQuestionPaymentIntentView.as_view(),
        name='response-question-payment-intent',
    ),
    path('answers/<int:pk>/payment-intent/', views.CreatePaymentIntentView.as_view(), name='answer-payment-intent'),
    path('answers/<int:pk>/confirm-payment/', views.ConfirmPaymentView.as_view(), name='answer-confirm-payment'),
    path('stripe/config/', views.StripeConfigView.as_view(), name='stripe-config'),
    path('stripe/webhook/', views.StripeWebhookView.as_view(), name='stripe-webhook'),

    # Admin: nested step CRUD
    path('questionnaires/<int:questionnaire_pk>/steps/', views.StepListCreateView.as_view(), name='step-list'),
    path('steps/<int:pk>/', views.StepDetailView.as_view(), name='step-detail'),

    # Administración: CRUD de preguntas anidadas
    path('steps/<int:step_pk>/questions/', views.QuestionListCreateView.as_view(), name='question-list'),
    path('questions/<int:pk>/', views.QuestionDetailView.as_view(), name='question-detail'),

    # Admin: nested option CRUD
    path('questions/<int:question_pk>/options/', views.OptionListCreateView.as_view(), name='option-list'),
    path('options/<int:pk>/', views.OptionDetailView.as_view(), name='option-detail'),

    # Asistente de preinscripción activo
    path('wizard/', views.WizardQuestionnaireView.as_view(), name='wizard-questionnaire'),
]
