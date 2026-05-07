from rest_framework import serializers

from academic.models import Career
from .models import (
    Questionnaire,
    QuestionnaireResponse,
    QuestionnaireStep,
    Question,
    QuestionAnswer,
    QuestionOption,
)


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'label', 'value', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'label',
            'help_text',
            'question_type',
            'is_required',
            'order',
            'depends_on',
            'depends_on_value',
            'config',
            'options',
        ]


class QuestionnaireStepSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionnaireStep
        fields = ['id', 'title', 'description', 'order', 'questions']


class QuestionnaireSerializer(serializers.ModelSerializer):
    steps = QuestionnaireStepSerializer(many=True, read_only=True)

    class Meta:
        model = Questionnaire
        fields = [
            'id',
            'title',
            'description',
            'flow_type',
            'career',
            'is_active',
            'is_preinscripcion_wizard',
            'steps',
        ]


class QuestionnaireListSerializer(serializers.ModelSerializer):
    career_name = serializers.SerializerMethodField()
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = Questionnaire
        fields = [
            'id',
            'title',
            'description',
            'flow_type',
            'career',
            'career_name',
            'is_active',
            'is_preinscripcion_wizard',
            'step_count',
            'created_at',
        ]

    def get_career_name(self, obj):
        return obj.career.name if obj.career else None

    def get_step_count(self, obj):
        return obj.steps.count()


class QuestionAnswerSerializer(serializers.ModelSerializer):
    question_label = serializers.SerializerMethodField()
    question_type = serializers.SerializerMethodField()
    career_names = serializers.SerializerMethodField()

    class Meta:
        model = QuestionAnswer
        fields = [
            'id',
            'question',
            'question_label',
            'question_type',
            'text_value',
            'file_value',
            'json_value',
            'career_names',
            'stripe_payment_intent_id',
            'stripe_payment_status',
        ]
        read_only_fields = ['stripe_payment_intent_id', 'stripe_payment_status']

    def get_question_label(self, obj):
        return obj.question.label

    def get_question_type(self, obj):
        return obj.question.question_type

    def get_career_names(self, obj):
        if obj.question.question_type != 'career_select':
            return None
        ids = obj.json_value
        if not isinstance(ids, list):
            return None
        career_map = {c.id: c.name for c in Career.objects.filter(id__in=ids).only('id', 'name')}
        return [career_map.get(cid, f"#{cid}") for cid in ids]


class QuestionnaireResponseSerializer(serializers.ModelSerializer):
    questionnaire_title = serializers.SerializerMethodField()
    answers = QuestionAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionnaireResponse
        fields = [
            'id',
            'questionnaire',
            'questionnaire_title',
            'status',
            'current_step',
            'answers',
            'created_at',
            'updated_at',
            'submitted_at',
        ]

    def get_questionnaire_title(self, obj):
        return obj.questionnaire.title


# ---- Serializadores de escritura usados por las vistas para operaciones de creación/actualización ----

class QuestionnaireWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questionnaire
        fields = [
            'id',
            'title',
            'description',
            'flow_type',
            'career',
            'is_active',
            'is_preinscripcion_wizard',
        ]


class QuestionnaireStepWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionnaireStep
        fields = ['id', 'title', 'description', 'order']


class QuestionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id',
            'label',
            'help_text',
            'question_type',
            'is_required',
            'order',
            'depends_on',
            'depends_on_value',
            'config',
        ]


class QuestionOptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'label', 'value', 'order']


class ResponseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionnaireResponse
        fields = ['status', 'current_step']

    def validate_status(self, value):
        # Las transiciones de estado se gestionan con endpoints dedicados; permite únicamente
        # draft→draft step navigation via PATCH here.
        if value == 'submitted':
            raise serializers.ValidationError(
                "Use the /submit/ endpoint to submit a response."
            )
        return value
