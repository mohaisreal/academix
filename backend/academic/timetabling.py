from django.db import transaction
from django.db.models import Q

from academic.models import (
    Class,
    Subject,
    Classroom,
    ScheduleAssignment,
    SchedulingConstraint,
    ConstraintViolation,
    TeacherSubjectDecision,
)


def _build_warning_summary(hard_violations, soft_violations, precondition_errors, class_preparation_errors, unresolved_teachers):
    blocking_reasons = []
    if hard_violations > 0:
        blocking_reasons.append('hard_violations')
    if precondition_errors:
        blocking_reasons.extend(precondition_errors)
    if class_preparation_errors:
        blocking_reasons.extend(class_preparation_errors)

    return {
        'has_warnings': bool(hard_violations or soft_violations or precondition_errors or class_preparation_errors or unresolved_teachers),
        'hard_violations': hard_violations,
        'soft_violations': soft_violations,
        'precondition_errors': precondition_errors,
        'class_preparation_errors': class_preparation_errors,
        'unresolved_teachers': unresolved_teachers,
        'blocks_publish': bool(blocking_reasons),
        'blocking_reasons': blocking_reasons,
    }


def build_warning_summary_for_run(run):
    metadata = (run.metadata or {}).get('generator', {})
    hard_rows = run.violations.filter(severity='hard').count() if run.pk else 0
    soft_rows = run.violations.filter(severity='soft').count() if run.pk else 0
    summary = metadata.get('warning_summary', {}) or {}
    hard_violations = max(int(summary.get('hard_violations', 0) or 0), hard_rows)
    soft_violations = max(int(summary.get('soft_violations', 0) or 0), soft_rows)
    precondition_errors = list(summary.get('precondition_errors', metadata.get('precondition_errors', [])))
    class_preparation_errors = list(summary.get('class_preparation_errors', metadata.get('class_preparation_errors', [])))
    unresolved_teachers = list(summary.get('unresolved_teachers', metadata.get('unresolved_teachers', [])))
    return _build_warning_summary(hard_violations, soft_violations, precondition_errors, class_preparation_errors, unresolved_teachers)


def _build_generator_metadata(classes_considered, sessions_requested, precondition_errors, class_preparation_errors):
    return {
        'strategy': 'greedy-v1',
        'classes_created': 0,
        'classes_considered': classes_considered,
        'sessions_requested': sessions_requested,
        'generated_assignments': 0,
        'unscheduled_sessions': 0,
        'hard_violations': 0,
        'soft_violations': 0,
        'precondition_errors': precondition_errors,
        'class_preparation_errors': class_preparation_errors,
        'unresolved_teachers': [],
    }


def _persist_warning_summary(run, metadata, hard_violations, soft_violations):
    summary = _build_warning_summary(
        hard_violations=hard_violations,
        soft_violations=soft_violations,
        precondition_errors=list(metadata.get('precondition_errors', [])),
        class_preparation_errors=list(metadata.get('class_preparation_errors', [])),
        unresolved_teachers=list(metadata.get('unresolved_teachers', [])),
    )
    metadata['warning_summary'] = summary
    run.metadata = {'generator': metadata}
    return summary


def _section_label_for_index(index):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    value = index + 1
    label = ''
    while value:
        value, remainder = divmod(value - 1, 26)
        label = alphabet[remainder] + label
    return label


def _base_class_defaults(subject, classroom, section_label='A', source_teacher_decision=None):
    return {
        'teacher': source_teacher_decision.teacher if source_teacher_decision and source_teacher_decision.teacher_id else None,
        'classroom': classroom,
        'max_students': classroom.capacity,
        'is_generated_by_timetable': True,
        'section_label': section_label,
        'source_teacher_decision': source_teacher_decision,
    }


def prepare_classes_for_period(period):
    decisions = list(
        TeacherSubjectDecision.objects.filter(period=period)
        .select_related('offering__subject', 'offering__subject__department', 'offering', 'teacher')
        .order_by('offering__subject_id', 'teacher_id', 'id')
    )
    active_subjects = list(Subject.objects.filter(is_active=True).select_related('department', 'department__teacher').order_by('id'))
    if not active_subjects and not decisions:
        return {'created': 0, 'errors': ['class_preparation_insufficient_subjects']}

    classrooms = list(Classroom.objects.order_by('id'))
    if not classrooms:
        return {'created': 0, 'errors': ['class_preparation_insufficient_classrooms']}

    created = 0
    if decisions:
        approved = []
        for d in decisions:
            # Filtro: solo las decisiones aprobadas cuya oferta está activa alimentan el generador.
            if d.decision != 'approved' or not d.offering.is_active:
                continue
            approved.append(d)

        by_subject = {}
        for decision in approved:
            subject_id = decision.offering.subject_id
            by_subject.setdefault(subject_id, []).append(decision)

        for subject_id, subject_decisions in by_subject.items():
            subject = subject_decisions[0].offering.subject
            for index, decision in enumerate(subject_decisions):
                classroom = classrooms[(subject_id + index) % len(classrooms)]
                defaults = _base_class_defaults(subject, classroom, section_label=_section_label_for_index(index), source_teacher_decision=decision)
                _, was_created = Class.objects.get_or_create(
                    period=period,
                    subject=subject,
                    section_label=defaults['section_label'],
                    defaults=defaults,
                )
                if was_created:
                    created += 1
    else:
        for index, subject in enumerate(active_subjects):
            classroom = classrooms[index % len(classrooms)]
            _, was_created = Class.objects.get_or_create(
                period=period,
                subject=subject,
                section_label='A',
                defaults=_base_class_defaults(subject, classroom),
            )
            if was_created:
                created += 1

    return {'created': created, 'errors': []}


def _slot_overlaps_constraint(slot, constraint):
    if slot.day_of_week != constraint.day_of_week:
        return False
    return slot.start_time < constraint.end_time and slot.end_time > constraint.start_time


def _resolve_teacher(cls):
    if cls.teacher_id:
        return cls.teacher, cls.teacher_id

    department = getattr(cls.subject, 'department', None)
    if department and department.teacher_id:
        return department.teacher, department.teacher_id

    return None, None


def backfill_generated_class_teachers():
    updated = 0
    skipped_empty = 0
    skipped_ambiguous = 0
    skipped_existing_teacher = Class.objects.filter(is_generated_by_timetable=True).exclude(teacher__isnull=True).count()

    generated_classes = (
        Class.objects.filter(is_generated_by_timetable=True, teacher__isnull=True)
        .select_related('subject', 'subject__department', 'subject__department__teacher')
        .order_by('id')
    )

    for cls in generated_classes:
        teacher_ids = list(
            ScheduleAssignment.objects.filter(run__status='published', cls=cls)
            .exclude(teacher__isnull=True)
            .values_list('teacher_id', flat=True)
            .distinct()
        )
        if not teacher_ids:
            skipped_empty += 1
            continue
        if len(teacher_ids) > 1:
            skipped_ambiguous += 1
            continue

        cls.teacher_id = teacher_ids[0]
        cls.save(update_fields=['teacher'])
        updated += 1

    return {
        'updated': updated,
        'skipped_existing_teacher': skipped_existing_teacher,
        'skipped_empty': skipped_empty,
        'skipped_ambiguous': skipped_ambiguous,
    }


def _is_blocked_by_constraints(cls, slot, constraints, teacher_id):
    for c in constraints:
        if not _slot_overlaps_constraint(slot, c):
            continue
        if c.kind == 'teacher_unavailable' and teacher_id and c.teacher_id == teacher_id:
            return True
        if c.kind == 'classroom_unavailable' and c.classroom_id == cls.classroom_id:
            return True
        if c.kind == 'subject_unavailable' and c.subject_id == cls.subject_id:
            return True
    return False


def generate_for_run(run):
    preparation = prepare_classes_for_period(run.period)
    classes = list(
        Class.objects.filter(period=run.period)
        .select_related('teacher', 'classroom', 'subject__department__teacher')
        .prefetch_related('subject__careers')
        .order_by('id')
    )
    slots = list(run.period.time_slots.all().order_by('day_of_week', 'start_time', 'id'))

    precondition_errors = []
    has_teacher_decisions = TeacherSubjectDecision.objects.filter(period=run.period).exists()
    if not classes and not preparation['errors'] and not has_teacher_decisions:
        precondition_errors.append('missing_classes')
    if not slots:
        precondition_errors.append('missing_time_slots')
    if any(cls.classroom_id is None for cls in classes):
        precondition_errors.append('missing_classrooms')

    if precondition_errors or preparation['errors']:
        sessions_requested = sum(max(0, cls.subject.hours_per_week) for cls in classes)
        metadata = _build_generator_metadata(
            classes_considered=len(classes),
            sessions_requested=sessions_requested,
            precondition_errors=precondition_errors,
            class_preparation_errors=preparation['errors'],
        )
        metadata['classes_created'] = preparation['created']
        _persist_warning_summary(run, metadata, hard_violations=0, soft_violations=0)
        run.status = 'failed'
        run.save(update_fields=['status', 'metadata', 'updated_at'])
        return run

    run.assignments.all().delete()
    run.violations.all().delete()

    constraints = list(SchedulingConstraint.objects.filter(
        is_active=True,
    ).filter(Q(scope='global') | Q(scope='period', period=run.period)))

    used_teachers = set()
    used_classrooms = set()
    used_days_by_class = {}
    used_days_by_subject = {}
    generated = 0
    unscheduled = 0
    unresolved_teachers = []
    sessions_requested = 0

    for cls in classes:
        class_demand = max(0, cls.subject.hours_per_week)
        sessions_requested += class_demand
        resolved_teacher, resolved_teacher_id = _resolve_teacher(cls)
        if resolved_teacher_id is None:
            unresolved_teachers.append(cls.id)
            unscheduled += class_demand
            ConstraintViolation.objects.create(
                run=run,
                assignment=None,
                severity='hard',
                reason='No se pudo resolver el docente de la clase.',
                metadata={
                    'class_id': cls.id,
                    'subject_name': cls.subject.name,
                    'subject_code': cls.subject.code,
                    'teacher_name': cls.teacher and (f"{cls.teacher.first_name} {cls.teacher.last_name}".strip() or cls.teacher.username) or None,
                    'unresolved_teacher': True,
                    'requested_sessions': class_demand,
                },
            )
            continue

        if cls.is_generated_by_timetable and cls.teacher_id is None:
            cls.teacher = resolved_teacher
            cls.save(update_fields=['teacher'])

        class_used_days = used_days_by_class.setdefault(cls.id, set())
        subject_used_days = used_days_by_subject.setdefault(cls.subject_id, set())
        for _session_index in range(class_demand):
            assigned = False
            for slot in slots:
                teacher_key = (slot.id, resolved_teacher_id)
                classroom_key = (slot.id, cls.classroom_id)
                if slot.day_of_week in class_used_days:
                    continue
                if slot.day_of_week in subject_used_days:
                    continue
                if resolved_teacher_id and teacher_key in used_teachers:
                    continue
                if cls.classroom_id and classroom_key in used_classrooms:
                    continue
                if _is_blocked_by_constraints(cls, slot, constraints, resolved_teacher_id):
                    continue

                ScheduleAssignment.objects.create(
                    run=run,
                    cls=cls,
                    slot=slot,
                    classroom=cls.classroom,
                    teacher=resolved_teacher,
                    source='generated',
                )
                class_used_days.add(slot.day_of_week)
                subject_used_days.add(slot.day_of_week)
                if resolved_teacher_id:
                    used_teachers.add(teacher_key)
                if cls.classroom_id:
                    used_classrooms.add(classroom_key)
                generated += 1
                assigned = True
                break

            if not assigned:
                unscheduled += 1
                ConstraintViolation.objects.create(
                    run=run,
                    assignment=None,
                    severity='hard',
                    reason='No hay franja disponible tras aplicar las restricciones activas.',
                    metadata={
                        'class_id': cls.id,
                        'subject_name': cls.subject.name,
                        'subject_code': cls.subject.code,
                        'teacher_name': cls.teacher and (f"{cls.teacher.first_name} {cls.teacher.last_name}".strip() or cls.teacher.username) or None,
                        'constraint_related': True,
                    },
                )

    hard_violations = unscheduled
    soft_violations = 0
    metadata = _build_generator_metadata(
        classes_considered=len(classes),
        sessions_requested=sessions_requested,
        precondition_errors=[],
        class_preparation_errors=preparation['errors'],
    )
    metadata['classes_created'] = preparation['created']
    metadata['generated_assignments'] = generated
    metadata['unscheduled_sessions'] = unscheduled
    metadata['hard_violations'] = hard_violations
    metadata['soft_violations'] = soft_violations
    metadata['unresolved_teachers'] = unresolved_teachers
    _persist_warning_summary(run, metadata, hard_violations=hard_violations, soft_violations=soft_violations)

    if generated == 0 and not has_teacher_decisions:
        run.status = 'failed'
    elif unscheduled > 0:
        run.status = 'partial'
    else:
        run.status = 'completed'

    run.save(update_fields=['status', 'metadata', 'updated_at'])
    return run


def delete_generated_classes_for_period(period, scope='period'):
    if scope != 'period':
        raise ValueError('Unsupported cleanup scope.')

    with transaction.atomic():
        classes_qs = Class.objects.filter(period=period, is_generated_by_timetable=True)
        deleted_count = classes_qs.count()
        classes_qs.delete()
    return deleted_count


def delete_generated_classes_for_decision(decision):
    with transaction.atomic():
        classes_qs = Class.objects.filter(
            source_teacher_decision=decision,
            is_generated_by_timetable=True,
        )
        deleted_count = classes_qs.count()
        classes_qs.delete()
    return deleted_count
