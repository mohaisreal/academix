"""
Data migration: seeds a Questionnaire that mirrors the static /admissions form,
so admins have a ready-made template to activate as the wizard.
"""
from django.db import migrations


TEMPLATE = {
    "title": "Preinscripción — Plantilla Base",
    "description": (
        "Plantilla que replica el formulario estático de preinscripción. "
        "Puedes activarla como asistente o usarla como punto de partida."
    ),
    "flow_type": "admissions",
    "steps": [
        {
            "title": "Vía de Acceso y Datos Académicos",
            "description": "Indica cómo accedes a la universidad y tus notas.",
            "order": 0,
            "questions": [
                {
                    "label": "Vía de acceso",
                    "help_text": "Selecciona la vía de acceso que corresponde a tu situación académica.",
                    "question_type": "radio",
                    "is_required": True,
                    "order": 0,
                    "config": {},
                    "options": [
                        {"label": "EvAU / EBAU (Bachillerato + Selectividad)", "value": "evau", "order": 0},
                        {"label": "Ciclo Formativo de Grado Superior (FP)", "value": "fp", "order": 1},
                        {"label": "Titulado Universitario", "value": "titulado", "order": 2},
                        {"label": "Mayores de 25 años", "value": "mayores_25", "order": 3},
                        {"label": "Mayores de 40 años", "value": "mayores_40", "order": 4},
                        {"label": "Mayores de 45 años", "value": "mayores_45", "order": 5},
                        {"label": "Acceso Internacional / Homologación", "value": "internacional", "order": 6},
                    ],
                },
                {
                    "label": "Nota media de Bachillerato o Ciclo Formativo (0,000 – 10,000)",
                    "help_text": "Nota media del expediente académico de Bachillerato o FP.",
                    "question_type": "number",
                    "is_required": False,
                    "order": 1,
                    "config": {"min": 0, "max": 10, "step": 0.001},
                    "options": [],
                },
                {
                    "label": "Nota de la Fase Obligatoria de la EvAU (0,000 – 10,000)",
                    "help_text": "Nota obtenida en la fase obligatoria de la Selectividad.",
                    "question_type": "number",
                    "is_required": False,
                    "order": 2,
                    "config": {"min": 0, "max": 10, "step": 0.001},
                    "options": [],
                },
                {
                    "label": "Asignaturas y notas de la Fase Voluntaria de la EvAU (JSON)",
                    "help_text": (
                        'Lista de asignaturas voluntarias en formato JSON. '
                        'Ejemplo: [{"subject": "Matemáticas", "grade": 8.5}]'
                    ),
                    "question_type": "textarea",
                    "is_required": False,
                    "order": 3,
                    "config": {},
                    "options": [],
                },
            ],
        },
        {
            "title": "Preferencias de Titulaciones",
            "description": "Selecciona las titulaciones a las que quieres acceder, ordenadas por preferencia (máx. 10).",
            "order": 1,
            "questions": [
                {
                    "label": "Titulaciones por orden de preferencia (máximo 10)",
                    "help_text": "Selecciona y ordená las carreras a las que quieres preinscribirte.",
                    "question_type": "career_select",
                    "is_required": True,
                    "order": 0,
                    "config": {"max_selections": 10},
                    "options": [],
                },
            ],
        },
        {
            "title": "Documentación",
            "description": "Adjunta los documentos requeridos según tu vía de acceso.",
            "order": 2,
            "questions": [
                {
                    "label": "DNI / NIE / Pasaporte",
                    "help_text": "Documento de identidad vigente (PDF, JPG o PNG, máx. 10 MB).",
                    "question_type": "file_upload",
                    "is_required": True,
                    "order": 0,
                    "config": {"accepted_types": ["pdf", "jpg", "jpeg", "png"], "max_size_mb": 10},
                    "options": [],
                },
                {
                    "label": "Credencial EvAU / EBAU (si aplica)",
                    "help_text": "Credencial oficial de Selectividad si tu vía de acceso es EvAU.",
                    "question_type": "file_upload",
                    "is_required": False,
                    "order": 1,
                    "config": {"accepted_types": ["pdf", "jpg", "jpeg", "png"], "max_size_mb": 10},
                    "options": [],
                },
                {
                    "label": "Certificado de Notas de Bachillerato o FP",
                    "help_text": "Expediente académico oficial de la etapa preuniversitaria.",
                    "question_type": "file_upload",
                    "is_required": False,
                    "order": 2,
                    "config": {"accepted_types": ["pdf", "jpg", "jpeg", "png"], "max_size_mb": 10},
                    "options": [],
                },
                {
                    "label": "Título Universitario (si aplica)",
                    "help_text": "Título universitario previo si accedes como titulado.",
                    "question_type": "file_upload",
                    "is_required": False,
                    "order": 3,
                    "config": {"accepted_types": ["pdf", "jpg", "jpeg", "png"], "max_size_mb": 10},
                    "options": [],
                },
            ],
        },
    ],
}


def create_template(apps, schema_editor):
    Questionnaire = apps.get_model('questionnaire', 'Questionnaire')
    QuestionnaireStep = apps.get_model('questionnaire', 'QuestionnaireStep')
    Question = apps.get_model('questionnaire', 'Question')
    QuestionOption = apps.get_model('questionnaire', 'QuestionOption')

    # Idempotente: omite si la plantilla ya existe
    if Questionnaire.objects.filter(title=TEMPLATE['title']).exists():
        return

    q = Questionnaire.objects.create(
        title=TEMPLATE['title'],
        description=TEMPLATE['description'],
        flow_type=TEMPLATE['flow_type'],
        is_active=True,
        is_preinscripcion_wizard=False,
        career=None,
        created_by=None,
    )

    for step_data in TEMPLATE['steps']:
        step = QuestionnaireStep.objects.create(
            questionnaire=q,
            title=step_data['title'],
            description=step_data['description'],
            order=step_data['order'],
        )
        for question_data in step_data['questions']:
            question = Question.objects.create(
                step=step,
                label=question_data['label'],
                help_text=question_data['help_text'],
                question_type=question_data['question_type'],
                is_required=question_data['is_required'],
                order=question_data['order'],
                config=question_data['config'],
            )
            for option_data in question_data['options']:
                QuestionOption.objects.create(
                    question=question,
                    label=option_data['label'],
                    value=option_data['value'],
                    order=option_data['order'],
                )


def remove_template(apps, schema_editor):
    Questionnaire = apps.get_model('questionnaire', 'Questionnaire')
    Questionnaire.objects.filter(title=TEMPLATE['title']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaire', '0002_questionnaire_is_preinscripcion_wizard'),
    ]

    operations = [
        migrations.RunPython(create_template, remove_template),
    ]
