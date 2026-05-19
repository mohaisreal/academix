from __future__ import annotations

import random
from datetime import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject, TimeSlot, TimetableRun
from academic.timetabling import generate_for_run
from admissions.models import AdmissionApplication, AdmissionPreference
from users.models import User


FIRST_NAMES = ["Lucía", "Martín", "Sofía", "Mateo", "Paula", "Diego", "Emma", "Nicolás"]
LAST_NAMES = ["García", "Rodríguez", "Martínez", "Sánchez", "Pérez", "López", "Gómez", "Ruiz"]


class Command(BaseCommand):
    help = "Seed reproducible/idempotent test data for admissions and timetable domains."

    def add_arguments(self, parser):
        parser.add_argument("--profile", type=str, default="full")
        parser.add_argument("--seed", type=int, default=20260519)
        parser.add_argument("--period-code", type=str, default="")
        parser.add_argument("--per-career", type=int, default=30)
        parser.add_argument("--students", type=int, default=0)
        parser.add_argument("--slots-per-day", type=int, default=5)
        parser.add_argument("--generate-run", action="store_true")
        parser.add_argument("--wipe-seed-data", action="store_true")

    def handle(self, *args, **options):
        profile = options["profile"]
        if profile not in {"full", "admissions", "timetable"}:
            raise CommandError("--profile must be one of: full, admissions, timetable.")

        per_career = options["per_career"]
        slots_per_day = options["slots_per_day"]
        if per_career <= 0:
            raise CommandError("--per-career must be greater than 0.")
        if slots_per_day <= 0:
            raise CommandError("--slots-per-day must be greater than 0.")

        period = self._resolve_period(options["period_code"])
        careers = self._resolve_careers()
        rng = random.Random(options["seed"])
        wipe_seed_data = options["wipe_seed_data"]

        summary = {
            "admissions": {"created": 0, "updated": 0, "existing": 0, "warnings": []},
            "timetable": {"created": 0, "updated": 0, "existing": 0, "warnings": []},
        }

        if wipe_seed_data:
            self._wipe_seed_data(profile=profile, period=period, summary=summary)

        if profile in {"admissions", "full"}:
            with transaction.atomic():
                self._seed_admissions(period, careers, per_career, rng, summary)

        if profile in {"timetable", "full"}:
            with transaction.atomic():
                self._seed_timetable(
                    period=period,
                    careers=careers,
                    rng=rng,
                    slots_per_day=slots_per_day,
                    generate_run=options["generate_run"],
                    summary=summary,
                )

        self._print_summary(profile, period, summary)

    def _resolve_period(self, period_code):
        if period_code:
            try:
                return AcademicPeriod.objects.get(code=period_code)
            except AcademicPeriod.DoesNotExist as exc:
                raise CommandError(f"AcademicPeriod with code '{period_code}' does not exist.") from exc

        period = AcademicPeriod.objects.filter(is_active=True).order_by("-start_date").first()
        if period:
            return period
        period = AcademicPeriod.objects.order_by("-start_date").first()
        if period:
            return period
        raise CommandError("No AcademicPeriod exists. Create one or run seed_base/seed_data first.")

    def _resolve_careers(self):
        careers = list(Career.objects.filter(is_active=True).order_by("code"))
        if not careers:
            raise CommandError("No active careers found. Create careers or run seed_base/seed_data first.")
        return careers

    def _seed_admissions(self, period, careers, per_career, rng, summary):
        global_number = 1
        for career in careers:
            career_slug = self._slug(career.code)
            for number in range(1, per_career + 1):
                username = f"seedtest_adm_{career_slug}_{number:03d}"
                first_name = FIRST_NAMES[(global_number + rng.randint(0, 100)) % len(FIRST_NAMES)]
                last_name = LAST_NAMES[(global_number + rng.randint(0, 100)) % len(LAST_NAMES)]
                dni = f"ADM{global_number:06d}"
                email = f"{username}@academix.test"

                user, created_user = User.objects.update_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "role": "s",
                        "first_name": first_name,
                        "last_name": last_name,
                        "dni": dni,
                        "is_active": True,
                        "email_verified": True,
                        "identity_verification_status": "approved",
                    },
                )
                user.set_password("AdmTest!123")
                user.save(update_fields=["password"])

                existing_app = AdmissionApplication.objects.filter(student=user, academic_period=period).first()
                app = existing_app or AdmissionApplication(student=user, academic_period=period)
                app.access_route = rng.choice(["evau", "fp", "internacional", "titulado"])
                app.bachillerato_grade = round(5 + rng.random() * 4.9, 3)
                app.evau_obligatory_grade = round(5 + rng.random() * 4.9, 3)
                app.evau_voluntary_subjects = [
                    {"subject": "Matemáticas II", "grade": round(5 + rng.random() * 4.9, 3)},
                    {"subject": "Física", "grade": round(5 + rng.random() * 4.9, 3)},
                ]
                app.admission_score = app.calculate_admission_score()
                app.status = "submitted"
                app.assigned_career = None
                app.assigned_preference_order = None
                app.notes = "Solicitud de prueba seed_test_data"
                app.save()

                app.preferences.all().delete()
                AdmissionPreference.objects.create(
                    application=app,
                    career=career,
                    preference_order=1,
                    status="pending",
                )

                if created_user:
                    summary["admissions"]["created"] += 1
                else:
                    summary["admissions"]["updated"] += 1
                if existing_app is None:
                    summary["admissions"]["created"] += 1
                else:
                    summary["admissions"]["updated"] += 1
                global_number += 1

    def _seed_timetable(self, period, careers, rng, slots_per_day, generate_run, summary):
        slots = self._seed_time_slots(period, slots_per_day)
        summary["timetable"]["created"] += slots["created"]
        summary["timetable"]["existing"] += slots["existing"]

        for career in careers:
            subject_code = f"SEEDSUB_{self._slug(career.code).upper()}"
            subject, subject_created = Subject.objects.get_or_create(
                code=subject_code,
                defaults={
                    "name": f"Asignatura de Prueba {career.code}",
                    "career": career,
                    "credits": 6,
                    "hours_per_week": 4,
                    "is_active": True,
                },
            )
            teacher_username = f"seedtest_teacher_{self._slug(career.code)}"
            teacher, teacher_created = User.objects.get_or_create(
                username=teacher_username,
                defaults={
                    "email": f"{teacher_username}@academix.test",
                    "role": "t",
                    "first_name": "Seed",
                    "last_name": career.code,
                    "is_active": True,
                },
            )
            classroom, classroom_created = Classroom.objects.get_or_create(
                name=f"AulaPrueba-{career.code}",
                defaults={"building": "Edificio de Prueba", "capacity": 50, "type": "lecture"},
            )
            _, class_created = Class.objects.get_or_create(
                subject=subject,
                teacher=teacher,
                period=period,
                defaults={"classroom": classroom, "max_students": 40},
            )

            summary["timetable"]["created"] += sum(
                [subject_created, teacher_created, classroom_created, class_created]
            )

        if generate_run:
            run = TimetableRun.objects.create(
                period=period,
                status="draft",
                metadata={"seed_source": "seed_test_data", "seed_period": period.code},
            )
            generate_for_run(run)
            summary["timetable"]["created"] += 1
            if run.status not in {"completed", "partial"}:
                summary["timetable"]["warnings"].append(
                    f"TimetableRun ended as '{run.status}'."
                )

    def _seed_time_slots(self, period, slots_per_day):
        created = 0
        existing = 0
        slot_hours = [8, 10, 12, 14, 16, 18, 20]
        max_slots = min(slots_per_day, len(slot_hours) - 1)
        for day in [0, 1, 2, 3, 4]:
            for i in range(max_slots):
                _, was_created = TimeSlot.objects.get_or_create(
                    period=period,
                    day_of_week=day,
                    start_time=time(slot_hours[i], 0),
                    end_time=time(slot_hours[i + 1], 0),
                )
                if was_created:
                    created += 1
                else:
                    existing += 1
        return {"created": created, "existing": existing}

    def _print_summary(self, profile, period, summary):
        self.stdout.write(f"profile={profile} period={period.code}")
        for domain in ["admissions", "timetable"]:
            counts = summary[domain]
            self.stdout.write(
                f"{domain}: created={counts['created']} updated={counts['updated']} "
                f"existing={counts['existing']} warnings={len(counts['warnings'])}"
            )
            for warning in counts["warnings"]:
                self.stdout.write(self.style.WARNING(f"  - {warning}"))

    def _wipe_seed_data(self, profile, period, summary):
        if profile in {"admissions", "full"}:
            self._wipe_admissions_seed_data(period, summary)
        if profile in {"timetable", "full"}:
            self._wipe_timetable_seed_data(period, summary)

    def _wipe_admissions_seed_data(self, period, summary):
        seed_students = User.objects.filter(username__startswith="seedtest_adm_")
        AdmissionApplication.objects.filter(student__in=seed_students).delete()
        seed_students.delete()
        summary["admissions"]["warnings"].append(
            f"wipe-seed-data: cleared admissions seed users/apps before reseeding ({period.code})."
        )

    def _wipe_timetable_seed_data(self, period, summary):
        seed_subject_codes = Subject.objects.filter(code__startswith="SEEDSUB_").values_list("code", flat=True)
        seed_classes_in_period = Class.objects.filter(period=period, subject__code__in=seed_subject_codes)

        runs_from_metadata = TimetableRun.objects.filter(
            period=period,
            metadata__seed_source="seed_test_data",
        )
        runs_from_seed_assignments = TimetableRun.objects.filter(
            period=period,
            assignments__cls__in=seed_classes_in_period,
        )
        TimetableRun.objects.filter(
            id__in=runs_from_metadata.values_list("id", flat=True)
        ).delete()
        TimetableRun.objects.filter(
            id__in=runs_from_seed_assignments.values_list("id", flat=True)
        ).delete()

        seed_classes_in_period.delete()
        Subject.objects.filter(code__startswith="SEEDSUB_").delete()
        Classroom.objects.filter(name__startswith="AulaPrueba-").delete()
        User.objects.filter(username__startswith="seedtest_teacher_").delete()

        summary["timetable"]["warnings"].append(
            "wipe-seed-data: kept TimeSlots untouched (not safely distinguishable from non-seed slots)."
        )

    def _slug(self, value):
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "career"
