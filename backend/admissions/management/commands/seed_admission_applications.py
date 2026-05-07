"""
Seed submitted admission applications for automatic admissions/ranking tests.

What it creates by default:
  - 30 student users per active career.
  - 1 submitted AdmissionApplication per generated student.
  - 1 AdmissionPreference per application, where the target career is the
    first preference.
  - Predictable credentials for manual login tests.

Usage:
  python manage.py seed_admission_applications
  python manage.py seed_admission_applications --per-career 50
  python manage.py seed_admission_applications --period-code SP2026

Default credentials pattern:
  username: admission_<career_code>_<number>
  password: AdmTest!<CAREER_CODE><number>
  example:  admission_cs_001 / AdmTest!CS001
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academic.models import AcademicPeriod, Career
from admissions.models import AdmissionApplication, AdmissionPreference
from users.models import User


try:
    from faker import Faker
except ImportError:  # pragma: no cover - depends on local/dev dependency set
    Faker = None


FIRST_NAMES = [
    "Lucía", "Martín", "Sofía", "Mateo", "Valeria", "Daniel", "Paula", "Hugo",
    "Emma", "Alejandro", "Noa", "Pablo", "Alba", "Adrián", "Carmen", "Diego",
    "Julia", "Mario", "Claudia", "Nicolás", "Irene", "Javier", "Marta", "Leo",
]

LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "Sánchez", "Pérez", "Gómez",
    "Fernández", "Moreno", "Jiménez", "Ruiz", "Hernández", "Díaz", "Álvarez",
    "Romero", "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos",
]

VOLUNTARY_SUBJECTS = [
    "Matemáticas II",
    "Física",
    "Química",
    "Biología",
    "Economía de la Empresa",
    "Dibujo Técnico",
    "Historia del Arte",
    "Latín II",
]


class Command(BaseCommand):
    help = "Create submitted admission applications for every active career."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-career",
            type=int,
            default=30,
            help="Number of submitted applications to create per career. Default: 30.",
        )
        parser.add_argument(
            "--period-code",
            type=str,
            default="",
            help="AcademicPeriod.code to use. Defaults to the active period, then latest period.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260505,
            help="Random seed for reproducible data. Default: 20260505.",
        )
        parser.add_argument(
            "--password-template",
            type=str,
            default="AdmTest!{career_code}{number:03d}",
            help=(
                "Password template. Available placeholders: "
                "{career_code}, {career_slug}, {number}, {global_number}."
            ),
        )
        parser.add_argument(
            "--include-inactive-careers",
            action="store_true",
            help="Also create applications for inactive careers.",
        )

    def handle(self, *args, **options):
        per_career = options["per_career"]
        if per_career <= 0:
            raise CommandError("--per-career must be greater than 0.")

        rng = random.Random(options["seed"])
        fake = Faker("es_ES") if Faker else None
        if fake:
            Faker.seed(options["seed"])

        period = self._get_period(options["period_code"])
        careers = self._get_careers(options["include_inactive_careers"])

        self.stdout.write("Seeding submitted admission applications...")
        self.stdout.write(f"  Period: {period.name} ({period.code})")
        self.stdout.write(f"  Careers: {len(careers)}")
        self.stdout.write(f"  Applications per career: {per_career}")

        created_users = 0
        updated_users = 0
        created_apps = 0
        updated_apps = 0
        credentials = []

        with transaction.atomic():
            global_number = 1
            for career in careers:
                career_slug = self._slug(career.code)
                career_code = career.code.upper()

                for number in range(1, per_career + 1):
                    username = f"admission_{career_slug}_{number:03d}"
                    password = options["password_template"].format(
                        career_code=career_code,
                        career_slug=career_slug,
                        number=number,
                        global_number=global_number,
                    )
                    first_name, last_name = self._person_name(fake, rng, global_number)
                    email = f"{username}@academix.test"
                    dni = f"ADM{global_number:06d}"

                    user, was_created = self._upsert_student(
                        username=username,
                        password=password,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        dni=dni,
                        fake=fake,
                        rng=rng,
                    )
                    created_users += int(was_created)
                    updated_users += int(not was_created)

                    app, app_was_created = self._upsert_submitted_application(
                        student=user,
                        period=period,
                        career=career,
                        rng=rng,
                        global_number=global_number,
                    )
                    created_apps += int(app_was_created)
                    updated_apps += int(not app_was_created)

                    credentials.append((career.code, username, password, app.admission_score))
                    global_number += 1

        self._print_summary(
            period=period,
            careers=careers,
            per_career=per_career,
            created_users=created_users,
            updated_users=updated_users,
            created_apps=created_apps,
            updated_apps=updated_apps,
            credentials=credentials,
        )

    def _get_period(self, period_code):
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
            self.stdout.write(self.style.WARNING(
                "  No active AcademicPeriod found. Falling back to latest period."
            ))
            return period

        raise CommandError("No AcademicPeriod exists. Run seed_base/seed_data or create a period first.")

    def _get_careers(self, include_inactive):
        qs = Career.objects.all().order_by("code")
        if not include_inactive:
            qs = qs.filter(is_active=True)
        careers = list(qs)
        if not careers:
            raise CommandError("No careers found. Run seed_base/seed_data or create careers first.")
        return careers

    def _upsert_student(self, username, password, email, first_name, last_name, dni, fake, rng):
        defaults = {
            "email": email,
            "role": "s",
            "first_name": first_name,
            "last_name": last_name,
            "dni": dni,
            "email_verified": True,
            "identity_verification_status": "approved",
            "is_active": True,
            "phone": self._phone(fake, rng),
            "address": fake.address() if fake else f"Calle de Prueba {rng.randint(1, 200)}, Madrid",
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=35) if fake else None,
        }
        user, created = User.objects.update_or_create(
            username=username,
            defaults=defaults,
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        return user, created

    def _upsert_submitted_application(self, student, period, career, rng, global_number):
        existing = (
            AdmissionApplication.objects
            .filter(student=student, academic_period=period)
            .order_by("id")
            .first()
        )

        # The model fields are max_digits=4, decimal_places=3, so 10.000 would
        # not fit even though the help_text says 0.000-10.000. Keep generated
        # persisted grades below 10.000 to avoid seeding invalid rows.
        bachillerato_grade = self._grade(rng, Decimal("5.000"), Decimal("9.990"))
        evau_obligatory_grade = self._grade(rng, Decimal("5.000"), Decimal("9.990"))
        voluntary = self._voluntary_subjects(rng)
        submission_date = timezone.now() - timedelta(minutes=global_number)

        app = existing or AdmissionApplication(student=student, academic_period=period)
        app.access_route = rng.choice(["evau", "fp", "titulado", "internacional"])
        app.bachillerato_grade = bachillerato_grade
        app.evau_obligatory_grade = evau_obligatory_grade
        app.evau_voluntary_subjects = voluntary
        app.admission_score = app.calculate_admission_score()
        app.assigned_career = None
        app.assigned_preference_order = None
        app.status = "submitted"
        app.submission_date = submission_date
        app.admission_expiry_date = None
        app.notes = "Solicitud de prueba generada para validar admisiones automáticas."
        app.save()

        # Idempotent reset for generated applications: the target career must be
        # the first preference so each career receives exactly `per_career`
        # candidates for ranking generation.
        app.preferences.all().delete()
        AdmissionPreference.objects.create(
            application=app,
            career=career,
            preference_order=1,
            status="pending",
        )
        return app, existing is None

    def _person_name(self, fake, rng, index):
        if fake:
            return fake.first_name(), f"{fake.last_name()} {fake.last_name()}"
        first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
        last_name = f"{LAST_NAMES[index % len(LAST_NAMES)]} {LAST_NAMES[(index * 7) % len(LAST_NAMES)]}"
        return first_name, last_name

    def _voluntary_subjects(self, rng):
        subjects = rng.sample(VOLUNTARY_SUBJECTS, k=2)
        return [
            {"subject": subjects[0], "grade": float(self._grade(rng, Decimal("5.000"), Decimal("9.990")))},
            {"subject": subjects[1], "grade": float(self._grade(rng, Decimal("5.000"), Decimal("9.990")))},
        ]

    def _grade(self, rng, minimum, maximum):
        raw = minimum + (maximum - minimum) * Decimal(str(rng.random()))
        return raw.quantize(Decimal("0.001"))

    def _phone(self, fake, rng):
        if fake:
            # Keep only digits because the model validator is strict.
            digits = "".join(ch for ch in fake.phone_number() if ch.isdigit())
            if 9 <= len(digits) <= 15:
                return f"+{digits}"
        return f"+346{rng.randint(10000000, 99999999)}"

    def _slug(self, value):
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "career"

    def _print_summary(
        self,
        period,
        careers,
        per_career,
        created_users,
        updated_users,
        created_apps,
        updated_apps,
        credentials,
    ):
        total_expected = len(careers) * per_career
        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write("  ADMISSION APPLICATION SEED SUMMARY")
        self.stdout.write("=" * 72)
        self.stdout.write(f"  Period:                 {period.name} ({period.code})")
        self.stdout.write(f"  Careers:                {len(careers)}")
        self.stdout.write(f"  Applications expected:  {total_expected}")
        self.stdout.write(f"  Users created/updated:  {created_users}/{updated_users}")
        self.stdout.write(f"  Apps created/updated:   {created_apps}/{updated_apps}")
        self.stdout.write("")
        self.stdout.write("  Credential pattern:")
        self.stdout.write("    username: admission_<career_code>_<number>")
        self.stdout.write("    password: AdmTest!<CAREER_CODE><number>")
        self.stdout.write("")
        self.stdout.write("  First credentials per career:")
        seen = set()
        for career_code, username, password, score in credentials:
            if career_code in seen:
                continue
            self.stdout.write(f"    {career_code:<8} {username:<24} / {password:<18} score={score}")
            seen.add(career_code)
        self.stdout.write("=" * 72)
        self.stdout.write(self.style.SUCCESS("✓ Submitted admission applications seeded successfully."))
