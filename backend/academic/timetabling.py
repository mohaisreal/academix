from academic.models import Class, ScheduleAssignment


def generate_for_run(run):
    classes = list(
        Class.objects.filter(period=run.period)
        .select_related('teacher', 'classroom')
        .order_by('id')
    )
    slots = list(run.period.time_slots.all().order_by('day_of_week', 'start_time', 'id'))

    precondition_errors = []
    if not classes:
        precondition_errors.append('missing_classes')
    if not slots:
        precondition_errors.append('missing_time_slots')
    if any(cls.teacher_id is None for cls in classes):
        precondition_errors.append('missing_teachers')
    if any(cls.classroom_id is None for cls in classes):
        precondition_errors.append('missing_classrooms')

    if precondition_errors:
        run.status = 'failed'
        run.metadata = {
            'generator': {
                'strategy': 'greedy-v1',
                'classes_considered': len(classes),
                'sessions_requested': len(classes),
                'generated_assignments': 0,
                'unscheduled_sessions': 0,
                'hard_violations': 0,
                'soft_violations': 0,
                'precondition_errors': precondition_errors,
            }
        }
        run.save(update_fields=['status', 'metadata', 'updated_at'])
        return run

    run.assignments.all().delete()
    run.violations.all().delete()

    used_teachers = set()
    used_classrooms = set()
    generated = 0
    unscheduled = 0

    for cls in classes:
        assigned = False
        for slot in slots:
            teacher_key = (slot.id, cls.teacher_id)
            classroom_key = (slot.id, cls.classroom_id)
            if cls.teacher_id and teacher_key in used_teachers:
                continue
            if cls.classroom_id and classroom_key in used_classrooms:
                continue

            ScheduleAssignment.objects.create(
                run=run,
                cls=cls,
                slot=slot,
                classroom=cls.classroom,
                teacher=cls.teacher,
                source='generated',
            )
            if cls.teacher_id:
                used_teachers.add(teacher_key)
            if cls.classroom_id:
                used_classrooms.add(classroom_key)
            generated += 1
            assigned = True
            break

        if not assigned:
            unscheduled += 1

    hard_violations = unscheduled
    soft_violations = 0
    run.metadata = {
        'generator': {
            'strategy': 'greedy-v1',
            'classes_considered': len(classes),
            'sessions_requested': len(classes),
            'generated_assignments': generated,
            'unscheduled_sessions': unscheduled,
            'hard_violations': hard_violations,
            'soft_violations': soft_violations,
            'precondition_errors': [],
        }
    }

    if generated == 0:
        run.status = 'failed'
    elif unscheduled > 0:
        run.status = 'partial'
    else:
        run.status = 'completed'

    run.save(update_fields=['status', 'metadata', 'updated_at'])
    return run
