from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('careers', views.CareerViewSet, basename='career')
router.register('subjects', views.SubjectViewSet, basename='subject')
router.register('departments', views.DepartmentViewSet, basename='department')
router.register('periods', views.AcademicPeriodViewSet, basename='period')
router.register('classrooms', views.ClassroomViewSet, basename='classroom')
router.register('classes', views.ClassViewSet, basename='class')
router.register('schedules', views.ClassScheduleViewSet, basename='schedule')
router.register('time-slots', views.TimeSlotViewSet, basename='time-slot')
router.register('timetable-runs', views.TimetableRunViewSet, basename='timetable-run')
router.register('schedule-assignments', views.ScheduleAssignmentViewSet, basename='schedule-assignment')
router.register('constraint-violations', views.ConstraintViolationViewSet, basename='constraint-violation')
router.register('scheduling-constraints', views.SchedulingConstraintViewSet, basename='scheduling-constraint')
router.register('offerings', views.SubjectOfferingViewSet, basename='offering')

urlpatterns = [
    path('teacher-subject-selection/submit/', views.TeacherSubjectSelectionSubmitView.as_view(), name='teacher-subject-selection-submit'),
    path('teacher-subject-selection/decisions/', views.TeacherSubjectDecisionListView.as_view(), name='teacher-subject-decision-list'),
    path('teacher-subject-selection/decisions/<int:pk>/review/', views.TeacherSubjectDecisionReviewView.as_view(), name='teacher-subject-decision-review'),
]

urlpatterns += router.urls
