from collections import defaultdict

from academic.models import ScheduleAssignment


def canonical_assignment_map_for_period(period_id, class_ids):
    assignments = (
        ScheduleAssignment.objects.filter(
            run__period_id=period_id,
            run__status='published',
            cls_id__in=class_ids,
        )
        .select_related('slot', 'teacher', 'classroom', 'run')
        .order_by('-run__created_at', '-id')
    )

    by_class = {}
    for assignment in assignments:
        if assignment.cls_id not in by_class:
            by_class[assignment.cls_id] = assignment
    return by_class


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
