from academic.models import ScheduleAssignment


def published_assignments_map_for_period(period_id, class_ids):
    assignments = (
        ScheduleAssignment.objects.filter(
            run__period_id=period_id,
            run__status='published',
            cls_id__in=class_ids,
        )
        .select_related('slot', 'teacher', 'classroom', 'run')
        .order_by('-run__created_at', 'slot__day_of_week', 'slot__start_time', 'id')
    )

    by_class = {class_id: [] for class_id in class_ids}
    for assignment in assignments:
        by_class.setdefault(assignment.cls_id, []).append(assignment)
    return by_class


def canonical_assignment_map_for_period(period_id, class_ids):
    grouped = published_assignments_map_for_period(period_id, class_ids)
    by_class = {}
    for class_id, assignments in grouped.items():
        if assignments:
            by_class[class_id] = assignments[0]
    return by_class


def resolve_assignment_teacher_for_class(cls, assignment_map=None):
    if cls.teacher_id:
        return cls.teacher
    if assignment_map is None:
        assignment_map = canonical_assignment_map_for_period(cls.period_id, [cls.id])
    assignment = assignment_map.get(cls.id)
    return assignment.teacher if assignment and assignment.teacher else None


def serialize_assignment_schedule(assignment):
    slot = assignment.slot
    return {
        'day_name': slot.get_day_of_week_display(),
        'start_time': slot.start_time.strftime('%H:%M'),
        'end_time': slot.end_time.strftime('%H:%M'),
        'source': assignment.source,
        'assignment_id': assignment.id,
    }


def schedules_overlap(first_assignment, second_assignment):
    a = first_assignment.slot
    b = second_assignment.slot
    if a.day_of_week != b.day_of_week:
        return False
    return not (a.end_time <= b.start_time or a.start_time >= b.end_time)
