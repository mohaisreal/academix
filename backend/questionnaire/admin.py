from django.contrib import admin

from .models import (
    Question,
    QuestionAnswer,
    QuestionnaireResponse,
    QuestionnaireStep,
    Questionnaire,
    QuestionOption,
)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1
    fields = ('label', 'value', 'order')
    ordering = ('order',)


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = (
        'label',
        'question_type',
        'is_required',
        'order',
        'help_text',
        'depends_on',
        'depends_on_value',
        'config',
    )
    ordering = ('order',)
    show_change_link = True


class QuestionnaireStepInline(admin.TabularInline):
    model = QuestionnaireStep
    extra = 0
    fields = ('title', 'order', 'description')
    ordering = ('order',)
    show_change_link = True


@admin.register(Questionnaire)
class QuestionnaireAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'flow_type',
        'career',
        'is_active',
        'step_count',
        'created_by',
        'created_at',
    )
    list_filter = ('flow_type', 'is_active', 'career')
    search_fields = ('title', 'description')
    raw_id_fields = ('career', 'created_by')
    inlines = [QuestionnaireStepInline]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'flow_type', 'is_active', 'career'),
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Steps')
    def step_count(self, obj):
        return obj.steps.count()


@admin.register(QuestionnaireStep)
class QuestionnaireStepAdmin(admin.ModelAdmin):
    list_display = ('title', 'questionnaire', 'order', 'question_count')
    list_filter = ('questionnaire__flow_type',)
    search_fields = ('title', 'questionnaire__title')
    raw_id_fields = ('questionnaire',)
    inlines = [QuestionInline]

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'label_short',
        'question_type',
        'step',
        'is_required',
        'order',
        'has_dependency',
    )
    list_filter = ('question_type', 'is_required', 'step__questionnaire__flow_type')
    search_fields = ('label', 'step__title', 'step__questionnaire__title')
    raw_id_fields = ('step', 'depends_on')
    inlines = [QuestionOptionInline]
    readonly_fields = ('id',)

    @admin.display(description='Label')
    def label_short(self, obj):
        return obj.label[:80] if len(obj.label) > 80 else obj.label

    @admin.display(description='Has dependency', boolean=True)
    def has_dependency(self, obj):
        return obj.depends_on is not None


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('label', 'value', 'question', 'order')
    search_fields = ('label', 'value', 'question__label')
    raw_id_fields = ('question',)


class QuestionAnswerInline(admin.TabularInline):
    model = QuestionAnswer
    extra = 0
    fields = (
        'question',
        'text_value',
        'json_value',
        'file_value',
        'stripe_payment_status',
    )
    raw_id_fields = ('question',)
    readonly_fields = ('stripe_payment_intent_id', 'stripe_payment_status')
    show_change_link = True


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'student',
        'questionnaire',
        'status',
        'current_step',
        'answer_count',
        'created_at',
        'submitted_at',
    )
    list_filter = ('status', 'questionnaire__flow_type', 'questionnaire')
    search_fields = ('student__username', 'student__email', 'questionnaire__title')
    raw_id_fields = ('questionnaire', 'student', 'admission')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at')
    inlines = [QuestionAnswerInline]

    @admin.display(description='Answers')
    def answer_count(self, obj):
        return obj.answers.count()


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'response',
        'question_short',
        'text_value_short',
        'stripe_payment_status',
    )
    list_filter = ('stripe_payment_status', 'question__question_type')
    search_fields = (
        'response__student__username',
        'question__label',
        'stripe_payment_intent_id',
    )
    raw_id_fields = ('response', 'question')
    readonly_fields = ('stripe_payment_intent_id',)

    @admin.display(description='Question')
    def question_short(self, obj):
        return obj.question.label[:60]

    @admin.display(description='Text value')
    def text_value_short(self, obj):
        return obj.text_value[:60] if obj.text_value else '—'
