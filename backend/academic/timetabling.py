from django.db.models import Q

from academic.models import Class, Subject, Classroom, ScheduleAssignment, SchedulingConstraint, ConstraintViolation


def _build_generator_metadata(classes_considered, precondition_errors, class_preparation_errors):
    return {
        'strategy': 'greedy-v1',
        'classes_created': 0,
        'classes_considered': classes_considered,
        'sessions_requested': classes_considered,
        'generated_assignments': 0,
        'unscheduled_sessions': 0,
        'hard_violations': 0,
        'soft_violations': 0,
        'precondition_errors': precondition_errors,
        'class_preparation_errors': class_preparation_errors,
        'unresolved_teachers': [],
    }


def prepare_classes_for_period(period):
    active_subjects = list(Subject.objects.filter(is_active=True).select_related('department', 'department__teacher').order_by('id'))
    if not active_subjects:
        return {'created': 0, 'errors': ['class_preparation_insufficient_subjects']}

    classrooms = list(Classroom.objects.order_by('id'))
    if not classrooms:
        return {'created': 0, 'errors': ['class_preparation_insufficient_classrooms']}

    created = 0
    for index, subject in enumerate(active_subjects):
        classroom = classrooms[index % len(classrooms)]
        _, was_created = Class.objects.get_or_create(
            period=period,
            subject=subject,
            defaults={
                'teacher': None,
                'classroom': classroom,
                'max_students': classroom.capacity,
            },
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


def _is_blocked_by_constraints(cls, slot, constraints, teacher_id):
    for c in constraints:
        if not _slot_overlaps_constraint(slot, c):
            continue
        if c.kind == 'teacher_unavailable' and teacher_id and c.teacher_id == teacher_id:
            return True
        if c.kind == 'classroom_unavailable' and c.classroom_id == cls.classroom_id:
            return True
        if c.kind == 'career_unavailable' and c.career_id == cls.subject.career_id:
            return True
    return False


def generate_for_run(run):
    preparation = prepare_classes_for_period(run.period)
    classes = list(
        Class.objects.filter(period=run.period)
        .select_related('teacher', 'classroom', 'subject__department__teacher')
        .order_by('id')
    )
    slots = list(run.period.time_slots.all().order_by('day_of_week', 'start_time', 'id'))

    precondition_errors = []
    if not classes and not preparation['errors']:
        precondition_errors.append('missing_classes')
    if not slots:
        precondition_errors.append('missing_time_slots')
    if any(cls.classroom_id is None for cls in classes):
        precondition_errors.append('missing_classrooms')

    if precondition_errors or preparation['errors']:
        metadata = _build_generator_metadata(
            classes_considered=len(classes),
            precondition_errors=precondition_errors,
            class_preparation_errors=preparation['errors'],
        )
        metadata['classes_created'] = preparation['created']
        run.status = 'failed'
        run.metadata = {'generator': metadata}
        run.save(update_fields=['status', 'metadata', 'updated_at'])
        return run

    run.assignments.all().delete()
    run.violations.all().delete()

    constraints = list(SchedulingConstraint.objects.filter(
        is_active=True,
    ).filter(Q(scope='global') | Q(scope='period', period=run.period)))

    used_teachers = set()
    used_classrooms = set()
    generated = 0
    unscheduled = 0
    unresolved_teachers = []

    for cls in classes:
        resolved_teacher, resolved_teacher_id = _resolve_teacher(cls)
        if resolved_teacher_id is None:
            unresolved_teachers.append(cls.id)
            unscheduled += 1
            ConstraintViolation.objects.create(
                run=run,
                assignment=None,
                severity='hard',
                reason='No teacher resolved for class (missing class teacher and department teacher).',
                metadata={'class_id': cls.id, 'unresolved_teacher': True},
            )
            continue

        assigned = False
        for slot in slots:
            teacher_key = (slot.id, resolved_teacher_id)
            classroom_key = (slot.id, cls.classroom_id)
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
                reason='No available slot after active scheduling constraints.',
                metadata={'class_id': cls.id, 'constraint_related': True},
            )

    hard_violations = unscheduled
    soft_violations = 0
    metadata = _build_generator_metadata(
        classes_considered=len(classes),
        precondition_errors=[],
        class_preparation_errors=preparation['errors'],
    )
    metadata['classes_created'] = preparation['created']
    metadata['generated_assignments'] = generated
    metadata['unscheduled_sessions'] = unscheduled
    metadata['hard_violations'] = hard_violations
    metadata['soft_violations'] = soft_violations
    metadata['unresolved_teachers'] = unresolved_teachers
    run.metadata = {'generator': metadata}

    if generated == 0:
        run.status = 'failed'
    elif unscheduled > 0:
        run.status = 'partial'
    else:
        run.status = 'completed'

    run.save(update_fields=['status', 'metadata', 'updated_at'])
    return run
