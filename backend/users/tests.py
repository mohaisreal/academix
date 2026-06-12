import re
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management import get_commands
from django.core.management.base import CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from academic.models import AcademicPeriod, Career, Classroom, Department, Subject, Class
from admissions.models import AdmissionApplication, AdmissionPreference
from enrollment.models import CareerEnrollment, ClassEnrollment, EnrollmentFee
from grades.models import Grade
from users.models import User


class SeedAcademicBaseCommandTests(TestCase):
    REALISTIC_CAREER_NAMES = {
        "Ingeniería en Sistemas",
        "Medicina",
        "Administración y Dirección de Empresas",
        "Arquitectura",
        "Psicología",
    }

    def _run_command(self):
        stdout = StringIO()
        call_command("seed_academic_base", stdout=stdout)
        return stdout.getvalue()

    def test_only_new_seed_command_exists_for_scope(self):
        commands = get_commands()
        self.assertIn("seed_academic_base", commands)
        self.assertNotIn("seed_base", commands)
        self.assertNotIn("seed_data", commands)
        self.assertNotIn("seed_test_data", commands)
        self.assertNotIn("seed_admission_applications", commands)

    def test_seed_cleans_only_target_entities(self):
        untouched_user = User.objects.create_user(username="gestion1", password="pass", role="m")
        untouched_period = AcademicPeriod.objects.create(
            name="Periodo Activo",
            code="PA2026",
            start_date="2026-01-10",
            end_date="2026-06-20",
            is_active=True,
        )
        old_career = Career.objects.create(name="Carrera Vieja", code="CV")
        Subject.objects.create(name="Asignatura Vieja", code="ASG000", career=old_career)
        Classroom.objects.create(name="Aula Vieja", building="Edificio Viejo", capacity=20, type="lecture")
        User.objects.create_user(username="estudiante150", password="pass", role="s")
        User.objects.create_user(username="profesor99", password="pass", role="t")

        self._run_command()

        self.assertTrue(User.objects.filter(id=untouched_user.id).exists())
        self.assertTrue(AcademicPeriod.objects.filter(id=untouched_period.id).exists())
        self.assertFalse(User.objects.filter(username="estudiante150").exists())
        self.assertFalse(User.objects.filter(username="profesor99").exists())
        self.assertGreater(User.objects.filter(role="s").count(), 0)
        self.assertGreater(User.objects.filter(role="t").count(), 0)
        self.assertGreater(Career.objects.count(), 0)
        self.assertGreater(Subject.objects.count(), 0)
        self.assertGreater(Classroom.objects.count(), 0)

    def test_seed_generates_realistic_catalog_without_generic_names(self):
        self._run_command()

        student_usernames = list(User.objects.filter(role="s").values_list("username", flat=True))
        self.assertTrue(all(re.match(r"^estudiante\d+$", username) for username in student_usernames))
        teacher_names = list(User.objects.filter(role="t").values_list("first_name", "last_name"))
        self.assertTrue(all(first and last for first, last in teacher_names))

        self.assertEqual(
            set(Career.objects.values_list("name", flat=True)),
            self.REALISTIC_CAREER_NAMES,
        )
        self.assertTrue(all(not re.match(r"^Asignatura\s+\d+$", s.name) for s in Subject.objects.all()))
        self.assertTrue(all(not re.match(r"^Carrera\s+\d+$", c.name) for c in Career.objects.all()))
        self.assertTrue(all(a.name.startswith("Aula ") for a in Classroom.objects.all()))

        self.assertEqual(Subject.objects.filter(careers__isnull=True).count(), 0)
        self.assertEqual(Career.objects.filter(subjects__isnull=True).count(), 0)

    def test_seed_assigns_numidif_only_to_students(self):
        self._run_command()

        students = list(User.objects.filter(role="s").order_by("id"))
        teachers = User.objects.filter(role="t")

        self.assertEqual(len(students), 100)
        self.assertEqual([student.dni for student in students], [f"NUMIDIF{i}" for i in range(1, 101)])
        self.assertTrue(all(re.fullmatch(r"NUMIDIF\d+", student.dni or "") for student in students))
        self.assertTrue(all(user.dni is None for user in teachers))
        self.assertEqual(User.objects.exclude(role="s").filter(dni__regex=r"^NUMIDIF\d+$").count(), 0)

    def test_seed_sets_all_careers_to_ten_spots_and_keeps_that_shape_on_rerun(self):
        self._run_command()

        first_snapshot = list(Career.objects.order_by("code").values_list("code", "total_spots"))

        self.assertEqual(len(first_snapshot), 5)
        self.assertTrue(all(total_spots == 10 for _, total_spots in first_snapshot))

        self._run_command()

        second_snapshot = list(Career.objects.order_by("code").values_list("code", "total_spots"))
        self.assertEqual(second_snapshot, first_snapshot)

    def test_seed_populates_shared_career_subject_relations(self):
        self._run_command()

        careers = Career.objects.prefetch_related("subjects").order_by("code")
        subjects = Subject.objects.prefetch_related("careers").order_by("code")

        self.assertTrue(all(career.subjects.count() > 0 for career in careers))
        self.assertTrue(all(subject.careers.count() > 0 for subject in subjects))
        self.assertTrue(all(subject.career_id is not None for subject in subjects))

    def test_seed_rerun_keeps_dni_sequence_deterministic_without_collisions(self):
        self._run_command()
        first_snapshot = list(User.objects.filter(role="s").order_by("id").values_list("dni", flat=True))

        self._run_command()

        second_snapshot = list(User.objects.filter(role="s").order_by("id").values_list("dni", flat=True))
        self.assertEqual(first_snapshot, [f"NUMIDIF{i}" for i in range(1, 101)])
        self.assertEqual(second_snapshot, first_snapshot)
        self.assertEqual(User.objects.filter(dni__regex=r"^NUMIDIF\d+$").count(), 100)

    def test_seed_creates_second_matriculation_demo_with_attempt_two_pricing(self):
        self._run_command()

        active_period = AcademicPeriod.objects.get(code="SEED-AP-01")
        prior_period = AcademicPeriod.objects.get(code="SEED-AP-00")
        student = User.objects.get(username="estudiante1")
        subject = Subject.objects.get(code="IS-ALG")
        current_class = Class.objects.get(period=active_period, subject=subject)
        current_enrollment = CareerEnrollment.objects.get(student=student, period=active_period, career=subject.career)
        fee = EnrollmentFee.objects.get(career_enrollment=current_enrollment)

        prior_enrollment = CareerEnrollment.objects.get(student=student, period=prior_period, career=subject.career)
        prior_class_enrollment = ClassEnrollment.objects.get(student=student, cls__period=prior_period, cls__subject=subject)
        prior_grade = Grade.objects.get(student=student, evaluation__cls=prior_class_enrollment.cls, evaluation__is_final_grade=True)

        self.assertEqual(prior_enrollment.status, "completed")
        self.assertEqual(prior_class_enrollment.status, "enrolled")
        self.assertLess(prior_grade.score, current_class.passing_grade)
        self.assertEqual(fee.line_items[0]["subject_code"], "IS-ALG")
        self.assertEqual(fee.line_items[0]["attempt_number"], 2)
        self.assertEqual(fee.line_items[0]["price_per_credit"], "28.00")
        self.assertEqual(fee.line_items[0]["subtotal"], "168.00")
        self.assertEqual(EnrollmentFee.objects.filter(career_enrollment__student=student, career_enrollment__career=subject.career, career_enrollment__period=active_period).count(), 1)

    def test_seed_creates_submitted_pending_admission_applications(self):
        active_period = AcademicPeriod.objects.create(
            name="Periodo de Admisión Vigente",
            code="PA-VIGENTE",
            start_date="2026-01-10",
            end_date="2026-06-20",
            is_active=True,
        )

        self._run_command()

        seeded_students = User.objects.filter(role="s")
        applications = AdmissionApplication.objects.all()

        self.assertEqual(applications.count(), 100)
        self.assertEqual(applications.filter(status="submitted").count(), applications.count())
        self.assertEqual(applications.exclude(submission_date__isnull=False).count(), 0)
        self.assertEqual(applications.exclude(student__role="s").count(), 0)
        self.assertEqual(applications.filter(academic_period__isnull=True).count(), 0)
        self.assertEqual(applications.exclude(academic_period=active_period).count(), 0)
        self.assertEqual(applications.exclude(status="submitted").count(), 0)

        self.assertEqual(
            {
                career_code: AdmissionApplication.objects.filter(assigned_career__code=career_code).count()
                for career_code in Career.objects.order_by("code").values_list("code", flat=True)
            },
            {career_code: 20 for career_code in Career.objects.order_by("code").values_list("code", flat=True)},
        )

    def test_seed_submitted_applications_include_target_career_and_payload(self):
        self._run_command()

        applications = AdmissionApplication.objects.select_related("student").all()

        self.assertGreater(applications.count(), 0)
        self.assertEqual(applications.exclude(status="submitted").count(), 0)
        self.assertEqual(applications.exclude(access_route="evau").count(), 0)
        self.assertEqual(applications.filter(bachillerato_grade__isnull=True).count(), 0)
        self.assertEqual(applications.filter(evau_obligatory_grade__isnull=True).count(), 0)
        self.assertEqual(applications.filter(admission_score__isnull=True).count(), 0)
        self.assertEqual(applications.exclude(admission_score=10.100).count(), 0)
        self.assertEqual(applications.filter(evau_voluntary_subjects=[]).count(), 0)
        self.assertEqual(applications.exclude(assigned_career__isnull=True).count(), applications.count())

        self.assertEqual(
            AdmissionPreference.objects.filter(application__in=applications).count(),
            applications.count(),
        )
        self.assertEqual(
            AdmissionPreference.objects.filter(application__in=applications, preference_order=1).count(),
            applications.count(),
        )
        self.assertEqual(
            AdmissionPreference.objects.filter(application__in=applications, status="pending").count(),
            applications.count(),
        )
        self.assertEqual(
            {
                career_code: AdmissionPreference.objects.filter(application__assigned_career__code=career_code).count()
                for career_code in Career.objects.order_by("code").values_list("code", flat=True)
            },
            {career_code: 20 for career_code in Career.objects.order_by("code").values_list("code", flat=True)},
        )

    def test_seed_creates_departments_and_links_subjects_and_teachers(self):
        self._run_command()

        departments = Department.objects.all()
        teachers = User.objects.filter(role="t")
        subjects = Subject.objects.all()

        self.assertGreater(departments.count(), 0)
        self.assertTrue(all(department.teacher_id is not None for department in departments))
        self.assertEqual(departments.values_list("teacher_id", flat=True).distinct().count(), departments.count())
        self.assertEqual(departments.exclude(teacher__role="t").count(), 0)
        self.assertEqual(User.objects.filter(role="t", department__isnull=True).count(), 0)
        self.assertEqual(User.objects.filter(role="t").exclude(department__in=departments).count(), 0)
        self.assertEqual(subjects.filter(department__isnull=True).count(), 0)
        self.assertEqual(subjects.exclude(department__in=departments).count(), 0)
        self.assertGreater(teachers.count(), departments.count())

    def test_seed_is_deterministic_for_catalog_names(self):
        self._run_command()
        first_snapshot = {
            "careers": tuple(Career.objects.order_by("code").values_list("code", "name")),
            "departments": tuple(Department.objects.order_by("code").values_list("code", "name")),
            "subjects": tuple(Subject.objects.order_by("code").values_list("code", "name", "career__code", "department__code")),
            "subject_careers": tuple(
                (
                    subject.code,
                    tuple(subject.careers.order_by("code").values_list("code", flat=True)),
                )
                for subject in Subject.objects.order_by("code")
            ),
        }

        self._run_command()
        second_snapshot = {
            "careers": tuple(Career.objects.order_by("code").values_list("code", "name")),
            "departments": tuple(Department.objects.order_by("code").values_list("code", "name")),
            "subjects": tuple(Subject.objects.order_by("code").values_list("code", "name", "career__code", "department__code")),
            "subject_careers": tuple(
                (
                    subject.code,
                    tuple(subject.careers.order_by("code").values_list("code", flat=True)),
                )
                for subject in Subject.objects.order_by("code")
            ),
        }

        self.assertEqual(first_snapshot, second_snapshot)

    def test_seed_fails_fast_when_timetable_readiness_is_insufficient(self):
        with patch(
            "users.management.commands.seed_academic_base.SEED_TIME_SLOTS",
            [(0, "08:00", "09:00")],
        ):
            with self.assertRaisesMessage(CommandError, "slots insuficientes"):
                self._run_command()

    def test_reexecution_replaces_departments_and_keeps_subject_department_links(self):
        self._run_command()
        first_department_ids = set(Department.objects.values_list("id", flat=True))

        self._run_command()

        second_department_ids = set(Department.objects.values_list("id", flat=True))
        self.assertEqual(Department.objects.count(), len(second_department_ids))
        self.assertTrue(first_department_ids.isdisjoint(second_department_ids))
        self.assertEqual(Subject.objects.filter(department__isnull=True).count(), 0)

    def test_reexecution_replaces_target_dataset(self):
        self._run_command()
        first_career_ids = set(Career.objects.values_list("id", flat=True))
        first_subject_ids = set(Subject.objects.values_list("id", flat=True))

        self._run_command()

        second_career_ids = set(Career.objects.values_list("id", flat=True))
        second_subject_ids = set(Subject.objects.values_list("id", flat=True))
        self.assertEqual(Career.objects.count(), len(second_career_ids))
        self.assertEqual(Subject.objects.count(), len(second_subject_ids))
        self.assertTrue(first_career_ids.isdisjoint(second_career_ids))
        self.assertTrue(first_subject_ids.isdisjoint(second_subject_ids))


class UserListViewFilteringTests(APITestCase):
    def setUp(self):
        self.management_user = User.objects.create_user(
            username="manager",
            email="manager@test.com",
            password="testpass123",
            role="m",
            first_name="Manager",
            last_name="User",
        )
        self.client.force_authenticate(user=self.management_user)

    def _create_user(self, index, *, first_name, last_name, role="s"):
        return User.objects.create_user(
            username=f"user_{index}",
            email=f"user_{index}@test.com",
            password="testpass123",
            first_name=first_name,
            last_name=last_name,
            role=role,
        )

    def _create_department(self, *, code="DEP-1", name="Departamento 1", teacher=None):
        return Department.objects.create(code=code, name=name, description="", teacher=teacher)

    def test_search_filters_across_full_dataset_before_pagination(self):
        for i in range(24):
            self._create_user(i, first_name=f"Alumno{i}", last_name="General", role="s")

        matched_user = self._create_user(99, first_name="Unique", last_name="Needle", role="s")

        response = self.client.get("/api/users/", {"search": "needle", "page": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], matched_user.id)

    def test_search_is_case_insensitive_and_matches_email(self):
        self._create_user(1, first_name="Alicia", last_name="One", role="s")
        matched_user = User.objects.create_user(
            username="mail_target",
            email="Needle.Target@Test.com",
            password="testpass123",
            first_name="Otro",
            last_name="Usuario",
            role="s",
        )

        response = self.client.get("/api/users/", {"search": "needle.target"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matched_user.id)

    def test_combined_role_search_and_page_return_filtered_subset_page(self):
        for i in range(45):
            role = "t" if i < 25 else "s"
            first_name = f"Alex{i}" if i < 25 else f"Alumno{i}"
            self._create_user(i, first_name=first_name, last_name="Filter", role=role)

        response = self.client.get(
            "/api/users/",
            {"role": "t", "search": "alex", "page": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertIsNotNone(response.data["previous"])
        self.assertIsNone(response.data["next"])
        self.assertEqual(len(response.data["results"]), 5)
        self.assertTrue(all(user["role"] == "t" for user in response.data["results"]))
        self.assertTrue(
            all("alex" in user["first_name"].lower() for user in response.data["results"])
        )

    def test_unknown_role_returns_valid_empty_paginated_payload(self):
        for i in range(8):
            self._create_user(i, first_name=f"Base{i}", last_name="User", role="s")

        response = self.client.get("/api/users/", {"role": "x"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_list_payload_exposes_department_for_management_prefill(self):
        department = self._create_department()
        user = self._create_user(1, first_name="Tea", last_name="Cher", role="t")
        user.department = department
        user.save(update_fields=["department"])

        response = self.client.get("/api/users/", {"role": "t"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["department"], department.id)
        self.assertEqual(response.data["results"][0]["department_name"], department.name)

    def test_teacher_save_persists_department_and_non_teacher_save_clears_it(self):
        department = self._create_department()

        create_response = self.client.post(
            "/api/users/",
            {
                "username": "teacher.department",
                "email": "teacher.department@test.com",
                "first_name": "Teacher",
                "last_name": "Dept",
                "role": "t",
                "department": department.id,
                "password": "testpass123",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["department"], department.id)
        self.assertEqual(create_response.data["department_name"], department.name)
        created = User.objects.get(username="teacher.department")
        self.assertEqual(created.department_id, department.id)

        patch_response = self.client.patch(
            f"/api/users/{created.id}/",
            {"role": "m", "department": department.id},
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(patch_response.data["department"])
        self.assertIsNone(patch_response.data["department_name"])
        created.refresh_from_db()
        self.assertIsNone(created.department_id)

    def test_non_teacher_payload_department_is_ignored_and_saved_as_null(self):
        department = self._create_department()

        response = self.client.post(
            "/api/users/",
            {
                "username": "student.department",
                "email": "student.department@test.com",
                "first_name": "Student",
                "last_name": "Dept",
                "role": "s",
                "department": department.id,
                "password": "testpass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["department"])
        self.assertIsNone(response.data["department_name"])
        self.assertIsNone(User.objects.get(username="student.department").department_id)


class IdentityVerificationDocumentAccessTests(APITestCase):
    def setUp(self):
        self.management_user = User.objects.create_user(
            username="manager-docs",
            email="manager-docs@test.com",
            password="testpass123",
            role="m",
            first_name="Manager",
            last_name="Docs",
        )
        self.student_user = User.objects.create_user(
            username="student-docs",
            email="student-docs@test.com",
            password="testpass123",
            role="s",
            first_name="Student",
            last_name="Docs",
            email_verified=True,
            identity_verification_status="pending",
        )

    def _create_document(self, *, name="dni.pdf", content=b"pdf-bytes"):
        return self.student_user.identity_documents.create(
            file=SimpleUploadedFile(name, content, content_type="application/pdf"),
            document_type="identity",
            original_filename=name,
        )

    def test_management_list_exposes_download_url_instead_of_raw_file_url(self):
        document = self._create_document()
        self.client.force_authenticate(user=self.management_user)

        response = self.client.get("/api/users/identity-verifications/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        payload = response.data["results"][0]["identity_documents"][0]
        self.assertNotIn("file", payload)
        self.assertEqual(payload["file_name"], "dni.pdf")
        self.assertEqual(
            payload["download_url"],
            f"/users/identity-verification-documents/{document.id}/download/",
        )

    def test_management_download_streams_document_and_rejects_non_management(self):
        document = self._create_document()

        self.client.force_authenticate(user=self.management_user)
        response = self.client.get(f"/api/users/identity-verification-documents/{document.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=\"dni.pdf\"", response["Content-Disposition"])
        self.assertEqual(response.getvalue(), b"pdf-bytes")

        self.client.force_authenticate(user=self.student_user)
        denied = self.client.get(f"/api/users/identity-verification-documents/{document.id}/download/")

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=None)
        anonymous = self.client.get(f"/api/users/identity-verification-documents/{document.id}/download/")

        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_download_missing_document_returns_not_found(self):
        self.client.force_authenticate(user=self.management_user)

        response = self.client.get("/api/users/identity-verification-documents/999999/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_missing_file_returns_not_found(self):
        document = self._create_document()
        document.file.delete(save=False)

        self.client.force_authenticate(user=self.management_user)
        response = self.client.get(f"/api/users/identity-verification-documents/{document.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
