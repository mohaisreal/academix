from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('careers', views.CareerViewSet, basename='career')
router.register('subjects', views.SubjectViewSet, basename='subject')
router.register('periods', views.AcademicPeriodViewSet, basename='period')
router.register('classrooms', views.ClassroomViewSet, basename='classroom')
router.register('classes', views.ClassViewSet, basename='class')
router.register('schedules', views.ClassScheduleViewSet, basename='schedule')
router.register('time-slots', views.TimeSlotViewSet, basename='time-slot')
router.register('timetable-runs', views.TimetableRunViewSet, basename='timetable-run')
router.register('schedule-assignments', views.ScheduleAssignmentViewSet, basename='schedule-assignment')
router.register('constraint-violations', views.ConstraintViolationViewSet, basename='constraint-violation')

urlpatterns = router.urls
