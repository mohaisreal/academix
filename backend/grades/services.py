from decimal import Decimal

from academic.models import Class
from .models import Evaluation, Grade


def _to_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_or_create_final_grade_evaluation(cls: Class):
    evaluation = (
        Evaluation.objects.filter(cls=cls, is_final_grade=True)
        .order_by('id')
        .first()
    )
    if evaluation:
        return evaluation, False

    return Evaluation.objects.get_or_create(
        cls=cls,
        is_final_grade=True,
        defaults={
            'name': 'Nota final',
            'type': 'exam',
            'max_score': Decimal('10'),
            'weight': Decimal('0'),
            'is_hidden': True,
        },
    )


def resolve_class_final_grade(student, cls: Class):
    final_grade_qs = (
        Grade.objects.filter(student=student, evaluation__cls=cls, evaluation__is_final_grade=True)
        .select_related('evaluation')
        .order_by('-graded_at', '-id')
    )
    grade = final_grade_qs.first()

    if grade:
        final_grade = _to_decimal(grade.score) if grade else None
        source = 'final_grade'
    else:
        grades = Grade.objects.filter(student=student, evaluation__cls=cls, evaluation__is_hidden=False)
        if not grades.exists():
            return {
                'final_grade': None,
                'source': 'none',
                'passed': None,
                'final_grade_visible': cls.show_final_grade_to_students,
            }
        total_weight = Decimal('0')
        weighted_sum = Decimal('0')
        for grade in grades.select_related('evaluation'):
            eval_weight = _to_decimal(grade.evaluation.weight or 0)
            max_score = _to_decimal(grade.evaluation.max_score or 0)
            if not max_score or max_score <= 0:
                continue
            normalized = _to_decimal(grade.score) / max_score * Decimal('10')
            weighted_sum += normalized * eval_weight
            total_weight += eval_weight
        if total_weight <= 0:
            return {
                'final_grade': None,
                'source': 'none',
                'passed': None,
                'final_grade_visible': cls.show_final_grade_to_students,
            }
        final_grade = (weighted_sum / total_weight).quantize(Decimal('0.01'))
        source = 'weighted_average'

    passed = None
    if final_grade is not None and cls.passing_grade is not None:
        passed = final_grade >= _to_decimal(cls.passing_grade)

    return {
        'final_grade': final_grade,
        'source': source,
        'passed': passed,
        'final_grade_visible': cls.show_final_grade_to_students,
    }
