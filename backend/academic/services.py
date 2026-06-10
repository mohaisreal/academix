from django.db import transaction

from enrollment.models import ClassEnrollment


def reconcile_teacher_decision_change(decision, previous_decision):
    """Preserva los registros de matrícula del alumnado cuando se revierte una decisión."""
    if previous_decision != 'approved' or decision.decision == 'approved':
        return 0

    from academic.models import Class

    with transaction.atomic():
        generated_classes = list(
            Class.objects.filter(
                source_teacher_decision=decision,
                is_generated_by_timetable=True,
            ).order_by('id')
        )
        if not generated_classes:
            return 0

        class_ids = [cls.id for cls in generated_classes]
        preserved = ClassEnrollment.objects.filter(cls_id__in=class_ids, status='enrolled')
        preserved.update(status='dropped', cls=None)

        deleted_count, _ = Class.objects.filter(id__in=class_ids).delete()
        return deleted_count
