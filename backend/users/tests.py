from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from academic.models import AcademicPeriod, Career, TimeSlot
from admissions.models import AdmissionApplication, AdmissionPreference
from users.models import User


class SeedTestDataCommandTests(TestCase):
    def setUp(self):
        self.period = AcademicPeriod.objects.create(
            name="Periodo Primavera 2026",
            code="SP2026",
            start_date="2026-02-01",
            end_date="2026-06-30",
            is_active=True,
        )
        self.career_cs = Career.objects.create(name="Ciencias de la Computación", code="CS", is_active=True)
        self.career_eng = Career.objects.create(name="Ingeniería", code="ENG", is_active=True)

    def _run_command(self, **kwargs):
        stdout = StringIO()
        call_command("seed_test_data", stdout=stdout, **kwargs)
        return stdout.getvalue()

    def test_rejects_invalid_profile(self):
        with self.assertRaises(CommandError):
            self._run_command(profile="bad")

    def test_rejects_non_positive_per_career(self):
        with self.assertRaises(CommandError):
            self._run_command(profile="admissions", per_career=0)

    def test_rejects_non_positive_slots_per_day(self):
        with self.assertRaises(CommandError):
            self._run_command(profile="timetable", slots_per_day=0)

    def test_rejects_unknown_period_code(self):
        with self.assertRaises(CommandError):
            self._run_command(profile="admissions", period_code="UNKNOWN")

    def test_rejects_when_no_careers_exist(self):
        Career.objects.all().delete()
        with self.assertRaises(CommandError):
            self._run_command(profile="admissions")

    def test_admissions_seed_is_idempotent_and_creates_preferences(self):
        self._run_command(profile="admissions", per_career=2, seed=20260519)

        first_usernames = list(
            User.objects.filter(username__startswith="seedtest_adm_")
            .order_by("username")
            .values_list("username", flat=True)
        )
        self.assertEqual(len(first_usernames), 4)
        self.assertEqual(AdmissionApplication.objects.count(), 4)
        self.assertEqual(AdmissionPreference.objects.count(), 4)
        self.assertEqual(
            AdmissionApplication.objects.filter(status="submitted", academic_period=self.period).count(),
            4,
        )

        self._run_command(profile="admissions", per_career=2, seed=20260519)

        second_usernames = list(
            User.objects.filter(username__startswith="seedtest_adm_")
            .order_by("username")
            .values_list("username", flat=True)
        )
        self.assertEqual(first_usernames, second_usernames)
        self.assertEqual(AdmissionApplication.objects.count(), 4)
        self.assertEqual(AdmissionPreference.objects.count(), 4)

    def test_seed_is_reproducible_with_same_seed(self):
        self._run_command(profile="admissions", per_career=1, seed=111)
        first_snapshot = list(
            User.objects.filter(username__startswith="seedtest_adm_")
            .order_by("username")
            .values_list("username", "first_name", "last_name", "dni")
        )

        AdmissionPreference.objects.all().delete()
        AdmissionApplication.objects.all().delete()
        User.objects.filter(username__startswith="seedtest_adm_").delete()

        self._run_command(profile="admissions", per_career=1, seed=111)
        second_snapshot = list(
            User.objects.filter(username__startswith="seedtest_adm_")
            .order_by("username")
            .values_list("username", "first_name", "last_name", "dni")
        )
        self.assertEqual(first_snapshot, second_snapshot)

    def test_timetable_profile_creates_time_slots(self):
        self._run_command(profile="timetable", slots_per_day=2, seed=20260519)
        self.assertEqual(TimeSlot.objects.filter(period=self.period).count(), 10)

    def test_wipe_seed_data_restarts_seed_records(self):
        self._run_command(profile="full", per_career=1, slots_per_day=2, seed=20260519)

        seeded_user = User.objects.filter(username__startswith="seedtest_adm_").order_by("id").first()
        original_seeded_user_id = seeded_user.id
        app = AdmissionApplication.objects.get(student=seeded_user, academic_period=self.period)
        app.notes = "mutado-manual"
        app.save(update_fields=["notes"])

        self._run_command(
            profile="full",
            per_career=1,
            slots_per_day=2,
            seed=20260519,
            wipe_seed_data=True,
        )

        self.assertEqual(User.objects.filter(username__startswith="seedtest_adm_").count(), 2)
        self.assertEqual(User.objects.filter(username__startswith="seedtest_teacher_").count(), 2)
        self.assertEqual(AdmissionApplication.objects.count(), 2)
        self.assertEqual(AdmissionPreference.objects.count(), 2)

        reseeded_user = User.objects.filter(username=seeded_user.username).first()
        self.assertIsNotNone(reseeded_user)
        self.assertNotEqual(reseeded_user.id, original_seeded_user_id)
        reseeded_app = AdmissionApplication.objects.get(student=reseeded_user, academic_period=self.period)
        self.assertNotEqual(reseeded_app.notes, "mutado-manual")

    def test_wipe_seed_data_does_not_delete_non_seed_records(self):
        non_seed_student = User.objects.create_user(
            username="normal_student",
            email="normal_student@test.com",
            password="testpass123",
            role="s",
        )
        non_seed_teacher = User.objects.create_user(
            username="normal_teacher",
            email="normal_teacher@test.com",
            password="testpass123",
            role="t",
        )
        external_app = AdmissionApplication.objects.create(
            student=non_seed_student,
            academic_period=self.period,
            status="submitted",
            notes="externa",
        )
        AdmissionPreference.objects.create(
            application=external_app,
            career=self.career_cs,
            preference_order=1,
            status="pending",
        )

        self._run_command(profile="full", per_career=1, slots_per_day=2, seed=20260519)
        self._run_command(
            profile="full",
            per_career=1,
            slots_per_day=2,
            seed=20260519,
            wipe_seed_data=True,
        )

        self.assertTrue(User.objects.filter(username="normal_student").exists())
        self.assertTrue(User.objects.filter(username="normal_teacher").exists())
        self.assertTrue(AdmissionApplication.objects.filter(id=external_app.id).exists())
        self.assertEqual(
            AdmissionPreference.objects.filter(application=external_app).count(),
            1,
        )


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
