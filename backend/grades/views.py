from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count

from .models import Evaluation, Grade
from .serializers import EvaluationSerializer, GradeSerializer
from academic.models import Class, AcademicPeriod
from enrollment.models import ClassEnrollment, CareerEnrollment
from notifications.utils import create_notification
from shared.permissions import IsStudent, IsTeacher, IsTeacherOrAdmin, IsAdminOrManagement

User = get_user_model()


class MyGradesView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        enrollments = ClassEnrollment.objects.filter(
            student=request.user, status='enrolled'
        ).select_related('cls__subject', 'cls__period', 'cls__teacher')
        if active_period:
            enrollments = enrollments.filter(cls__period=active_period)

        result = []
        for enr in enrollments:
            evals = list(Evaluation.objects.filter(cls=enr.cls).order_by('due_date'))
            grades_map = {
                g.evaluation_id: g
                for g in Grade.objects.filter(student=request.user, evaluation__in=evals)
            }
            eval_data = []
            for ev in evals:
                g = grades_map.get(ev.id)
                pct = None
                if g and ev.max_score and ev.max_score > 0:
                    pct = round(float(g.score) / float(ev.max_score) * 100, 1)
                eval_data.append({
                    'id': ev.id, 'name': ev.name, 'type': ev.type,
                    'type_display': ev.get_type_display(),
                    'max_score': float(ev.max_score),
                    'due_date': str(ev.due_date) if ev.due_date else None,
                    'score': float(g.score) if g else None,
                    'percentage': pct,
                    'feedback': g.feedback if g else '',
                    'graded_at': g.graded_at.isoformat() if g else None,
                })
            scores = [e['score'] for e in eval_data if e['score'] is not None]
            result.append({
                'class_id': enr.cls.id,
                'subject_name': enr.cls.subject.name,
                'subject_code': enr.cls.subject.code,
                'teacher_name': (
                    f"{enr.cls.teacher.first_name} {enr.cls.teacher.last_name}".strip()
                    if enr.cls.teacher else ''
                ),
                'period_name': enr.cls.period.name,
                'evaluations': eval_data,
                'average': round(sum(scores) / len(scores), 1) if scores else None,
            })
        return Response(result)


class MyFileView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        enrollments = (
            CareerEnrollment.objects
            .filter(student=request.user)
            .select_related('career', 'period')
            .order_by('-period__start_date')
        )
        periods_data = []
        for ce in enrollments:
            class_enrollments = ClassEnrollment.objects.filter(
                student=request.user, cls__period=ce.period
            ).select_related('cls__subject')
            subjects_data = []
            period_scores = []
            for class_enr in class_enrollments:
                evals = Evaluation.objects.filter(cls=class_enr.cls)
                grades = Grade.objects.filter(student=request.user, evaluation__in=evals)
                avg = grades.aggregate(a=Avg('score'))['a']
                if avg is not None:
                    period_scores.append(float(avg))
                subjects_data.append({
                    'subject_name': class_enr.cls.subject.name,
                    'subject_code': class_enr.cls.subject.code,
                    'credits': class_enr.cls.subject.credits,
                    'final_grade': round(float(avg), 1) if avg is not None else None,
                    'passed': float(avg) >= 50 if avg is not None else None,
                })
            periods_data.append({
                'period_name': ce.period.name,
                'career_name': ce.career.name,
                'status': ce.status,
                'status_display': ce.get_status_display(),
                'subjects': subjects_data,
                'period_gpa': round(sum(period_scores) / len(period_scores), 1) if period_scores else None,
            })

        all_grades = Grade.objects.filter(student=request.user)
        overall_avg = all_grades.aggregate(a=Avg('score'))['a']
        return Response({
            'student': {
                'id': request.user.id,
                'username': request.user.username,
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
                'phone': request.user.phone,
                'date_of_birth': str(request.user.date_of_birth) if request.user.date_of_birth else None,
                'profile_image': request.user.profile_image.url if request.user.profile_image else None,
            },
            'overall_gpa': round(float(overall_avg), 1) if overall_avg is not None else None,
            'periods': periods_data,
        })


class StudentFilesView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        if request.user.role == 't':
            student_ids = ClassEnrollment.objects.filter(
                cls__teacher=request.user, status='enrolled'
            ).values_list('student_id', flat=True).distinct()
            students = User.objects.filter(id__in=student_ids, role='s')
        else:
            students = User.objects.filter(role='s', is_active=True)
            career_id = self.request.query_params.get('career')
            period_id = self.request.query_params.get('period')
            if career_id:
                sids = CareerEnrollment.objects.filter(career_id=career_id).values_list('student_id', flat=True)
                students = students.filter(id__in=sids)
            if period_id:
                sids = CareerEnrollment.objects.filter(period_id=period_id).values_list('student_id', flat=True)
                students = students.filter(id__in=sids)

        result = []
        for s in students:
            avg = Grade.objects.filter(student=s).aggregate(a=Avg('score'))['a']
            active_enr = (
                CareerEnrollment.objects
                .filter(student=s, status='active')
                .select_related('career', 'period')
                .first()
            )
            result.append({
                'id': s.id,
                'username': s.username,
                'full_name': f"{s.first_name} {s.last_name}".strip() or s.username,
                'email': s.email,
                'career': active_enr.career.name if active_enr else None,
                'period': active_enr.period.name if active_enr else None,
                'gpa': round(float(avg), 1) if avg is not None else None,
                'is_active': s.is_active,
            })
        return Response(result)


class StudentFileDetailView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request, student_id):
        try:
            student = User.objects.get(pk=student_id, role='s')
        except User.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        enrollments = (
            CareerEnrollment.objects
            .filter(student=student)
            .select_related('career', 'period')
            .order_by('-period__start_date')
        )
        periods_data = []
        for ce in enrollments:
            class_enrollments = ClassEnrollment.objects.filter(
                student=student, cls__period=ce.period
            ).select_related('cls__subject', 'cls__teacher')
            subjects_data = []
            for class_enr in class_enrollments:
                evals = Evaluation.objects.filter(cls=class_enr.cls)
                grades = Grade.objects.filter(student=student, evaluation__in=evals)
                avg = grades.aggregate(a=Avg('score'))['a']
                subjects_data.append({
                    'subject_name': class_enr.cls.subject.name,
                    'subject_code': class_enr.cls.subject.code,
                    'credits': class_enr.cls.subject.credits,
                    'teacher': (
                        f"{class_enr.cls.teacher.first_name} {class_enr.cls.teacher.last_name}".strip()
                        if class_enr.cls.teacher else ''
                    ),
                    'final_grade': round(float(avg), 1) if avg is not None else None,
                    'passed': float(avg) >= 50 if avg is not None else None,
                })
            periods_data.append({
                'period_name': ce.period.name,
                'career_name': ce.career.name,
                'status': ce.get_status_display(),
                'subjects': subjects_data,
            })

        overall_avg = Grade.objects.filter(student=student).aggregate(a=Avg('score'))['a']
        return Response({
            'student': {
                'id': student.id,
                'username': student.username,
                'full_name': f"{student.first_name} {student.last_name}".strip() or student.username,
                'email': student.email,
                'phone': student.phone,
                'date_of_birth': str(student.date_of_birth) if student.date_of_birth else None,
            },
            'overall_gpa': round(float(overall_avg), 1) if overall_avg is not None else None,
            'periods': periods_data,
        })


class EvaluationListCreateView(ListCreateAPIView):
    serializer_class = EvaluationSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsTeacher()]

    def get_queryset(self):
        qs = Evaluation.objects.select_related('cls').all()
        class_id = self.request.query_params.get('class')
        if class_id:
            qs = qs.filter(cls_id=class_id)
        if self.request.user.role == 't':
            qs = qs.filter(cls__teacher=self.request.user)
        return qs


class MarkingView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, eval_id):
        try:
            evaluation = Evaluation.objects.select_related('cls__teacher').get(
                pk=eval_id, cls__teacher=request.user
            )
        except Evaluation.DoesNotExist:
            return Response({'error': 'Evaluation not found or not yours'}, status=404)

        enrolled = ClassEnrollment.objects.filter(
            cls=evaluation.cls, status='enrolled'
        ).select_related('student')
        grades_map = {g.student_id: g for g in Grade.objects.filter(evaluation=evaluation)}

        students_data = []
        for enr in enrolled:
            s = enr.student
            g = grades_map.get(s.id)
            students_data.append({
                'student_id': s.id,
                'full_name': f"{s.first_name} {s.last_name}".strip() or s.username,
                'username': s.username,
                'grade_id': g.id if g else None,
                'score': float(g.score) if g else None,
                'feedback': g.feedback if g else '',
                'graded_at': g.graded_at.isoformat() if g else None,
            })
        return Response({
            'evaluation': EvaluationSerializer(evaluation).data,
            'students': students_data,
        })

    def post(self, request, eval_id):
        try:
            evaluation = Evaluation.objects.select_related('cls__teacher').get(
                pk=eval_id, cls__teacher=request.user
            )
        except Evaluation.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        student_id = request.data.get('student_id')
        score = request.data.get('score')
        feedback = request.data.get('feedback', '')
        if not student_id or score is None:
            return Response({'error': 'student_id and score are required'}, status=400)

        try:
            student = User.objects.get(pk=student_id, role='s')
        except User.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        previous_grade = Grade.objects.filter(student=student, evaluation=evaluation).first()
        previous_score = previous_grade.score if previous_grade else None
        previous_feedback = previous_grade.feedback if previous_grade else ''

        grade, created = Grade.objects.update_or_create(
            student=student, evaluation=evaluation,
            defaults={'score': score, 'feedback': feedback, 'graded_by': request.user},
        )

        should_notify = (
            created
            or str(previous_score) != str(grade.score)
            or previous_feedback != grade.feedback
        )
        if should_notify:
            subject_name = evaluation.cls.subject.name
            teacher_name = request.user.get_full_name() or request.user.username
            create_notification(
                user=student,
                title='Nueva calificación disponible' if created else 'Calificación actualizada',
                message=(
                    f'Se ha {"registrado" if created else "actualizado"} tu calificación '
                    f'en {evaluation.name} ({subject_name}): {grade.score}/{evaluation.max_score}.'
                ),
                notif_type='success',
                event_type='grade_recorded',
                context={
                    'subject_name': subject_name,
                    'evaluation_name': evaluation.name,
                    'score': str(grade.score),
                    'max_score': str(evaluation.max_score),
                    'feedback': grade.feedback or '',
                    'teacher_name': teacher_name,
                },
            )
        return Response(GradeSerializer(grade).data, status=201 if created else 200)


class ClassReportView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request, class_id):
        try:
            cls = Class.objects.select_related('subject', 'period').get(pk=class_id)
        except Class.DoesNotExist:
            return Response({'error': 'Class not found'}, status=404)
        if request.user.role == 't' and cls.teacher != request.user:
            return Response({'error': 'Not your class'}, status=403)

        enrolled_ids = list(
            ClassEnrollment.objects.filter(cls=cls, status='enrolled')
            .values_list('student_id', flat=True)
        )
        evals = Evaluation.objects.filter(cls=cls)
        all_grades = Grade.objects.filter(evaluation__in=evals, student__in=enrolled_ids)
        total = len(enrolled_ids)

        per_student: dict = {}
        for g in all_grades:
            per_student.setdefault(g.student_id, []).append(float(g.score))

        pass_count = fail_count = 0
        student_avgs = []
        for sid, scores in per_student.items():
            sa = sum(scores) / len(scores)
            student_avgs.append((sid, sa))
            if sa >= 50:
                pass_count += 1
            else:
                fail_count += 1

        student_avgs.sort(key=lambda x: x[1], reverse=True)

        def build_list(pairs):
            result = []
            for sid, sa in pairs:
                try:
                    u = User.objects.get(pk=sid)
                    result.append({
                        'name': f"{u.first_name} {u.last_name}".strip() or u.username,
                        'avg': round(sa, 1),
                    })
                except User.DoesNotExist:
                    pass
            return result

        top5 = build_list(student_avgs[:5])
        bottom5 = build_list(list(reversed(student_avgs[-5:])))

        eval_stats = []
        for ev in evals:
            ev_grades = all_grades.filter(evaluation=ev)
            ev_avg = ev_grades.aggregate(a=Avg('score'))['a']
            eval_stats.append({
                'name': ev.name,
                'type': ev.type,
                'type_display': ev.get_type_display(),
                'avg_score': round(float(ev_avg), 1) if ev_avg is not None else None,
                'average_score': round(float(ev_avg), 1) if ev_avg is not None else None,
                'submission_rate': round(ev_grades.count() / total * 100, 1) if total > 0 else 0,
                'max_score': float(ev.max_score),
            })

        global_avg = all_grades.aggregate(a=Avg('score'))['a']
        mean = round(float(global_avg), 1) if global_avg is not None else None
        pass_rate = round(pass_count / total * 100, 1) if total > 0 else 0
        student_scores = [round(sa, 1) for _, sa in student_avgs]
        return Response({
            'class': {
                'id': cls.id,
                'subject_name': cls.subject.name,
                'period': cls.period.name,
            },
            'stats': {
                'total_students': total,
                'mean': mean,
                'pass_count': pass_count,
                'fail_count': fail_count,
                'pass_rate': pass_rate,
            },
            # Campos de compatibilidad consumidos por la página actual de informes de Astro.
            'total_students': total,
            'mean_score': mean,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'failed_count': fail_count,
            'pass_rate': pass_rate,
            'student_scores': student_scores,
            'top_students': top5,
            'bottom_students': bottom5,
            'evaluations': eval_stats,
            'evaluation_stats': eval_stats,
            'evaluations_performance': eval_stats,
        })


class StatisticsView(APIView):
    permission_classes = [IsAdminOrManagement]

    def get(self, request):
        from academic.models import Career

        total_students = User.objects.filter(role='s', is_active=True).count()
        total_teachers = User.objects.filter(role='t', is_active=True).count()
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        active_classes = Class.objects.filter(period=active_period).count() if active_period else 0
        active_enrolments = CareerEnrollment.objects.filter(status='active').count()

        all_grades = Grade.objects.all()
        total_grades = all_grades.count()
        pass_grades = sum(1 for g in all_grades if g.score >= 50)
        pass_rate = round(pass_grades / total_grades * 100, 1) if total_grades > 0 else 0
        platform_gpa = round(float(all_grades.aggregate(a=Avg('score'))['a']), 1) if total_grades > 0 else None

        career_stats = []
        for c in Career.objects.filter(is_active=True):
            student_ids = CareerEnrollment.objects.filter(
                career=c, status='active'
            ).values_list('student_id', flat=True)
            grades = Grade.objects.filter(student__in=student_ids)
            avg = grades.aggregate(a=Avg('score'))['a']
            career_total_grades = grades.count()
            career_pass_grades = sum(1 for g in grades if g.score >= 50)
            career_pass_rate = (
                round(career_pass_grades / career_total_grades * 100, 1)
                if career_total_grades > 0 else 0
            )
            career_class_count = Class.objects.filter(subject__career=c).count()
            career_stats.append({
                'career_name': c.name,
                'students': student_ids.count(),
                'avg_gpa': round(float(avg), 1) if avg is not None else None,
                'classes': career_class_count,
                # Campos de compatibilidad consumidos por la página actual de Astro.
                'name': c.name,
                'student_count': student_ids.count(),
                'active_classes': career_class_count,
                'pass_rate': career_pass_rate,
            })

        enrolment_by_status = {
            row['status']: row['count']
            for row in CareerEnrollment.objects.values('status').annotate(count=Count('id'))
        }

        return Response({
            'kpis': {
                'total_students': total_students,
                'total_teachers': total_teachers,
                'active_classes': active_classes,
                'active_enrolments': active_enrolments,
                'pass_rate': pass_rate,
                'platform_gpa': platform_gpa,
            },
            # Campos de compatibilidad consumidos por la página actual de estadísticas de Astro.
            'total_students': total_students,
            'total_teachers': total_teachers,
            'active_classes': active_classes,
            'active_enrolments': active_enrolments,
            'pass_rate': pass_rate,
            'platform_gpa': platform_gpa,
            'enrolment_by_status': enrolment_by_status,
            'career_stats': career_stats,
        })
