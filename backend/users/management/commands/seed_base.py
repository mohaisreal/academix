"""
seed_base.py — Wipe & reseed with a minimal base for enrollment testing.

What it creates:
  - 1 admin (admin / admin123)
  - 2 management (mgmt1, mgmt2 / <username>123)
  - 10 teachers (teacher01..teacher10 / <username>123)
  - NO students — create one manually via /register to test enrollment

Academic structure:
  - 3 careers (CS, BA, ENG)
  - 5 subjects per career (15 total)
  - 1 active academic period (Spring 2026)
  - 8 classrooms (4 lecture + 4 lab, capacity 30)
  - 15 classes (one per subject for the active period)
  - 2 schedules per class (non-overlapping)
  - 3 evaluations per class (Midterm, Assignment 1, Quiz 1)

What it does NOT create:
  - Students
  - CareerEnrollments / ClassEnrollments
  - Grades
  - Notifications
  - Messages
  - AdmissionApplications

Usage:
  python manage.py seed_base            # wipe + reseed
  python manage.py seed_base --no-wipe  # reseed without wiping (idempotent)
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------
CAREERS_DATA = [
    ("Computer Science",       "CS",  4, 50, "Bachelor's degree in Computer Science and Software Engineering."),
    ("Business Administration", "BA",  3, 40, "Bachelor's degree in Business Administration and Gestión."),
    ("Engineering",             "ENG", 5, 45, "Bachelor's degree in Mechanical and Civil Engineering."),
]

SUBJECTS_DATA = {
    "CS": [
        ("Calculus I",        "CS101", 4, 6),
        ("Programming I",     "CS102", 4, 6),
        ("Data Structures",   "CS103", 3, 4),
        ("Databases",         "CS104", 3, 4),
        ("Computer Networks", "CS105", 3, 5),
    ],
    "BA": [
        ("Business Economics",   "BA101", 3, 4),
        ("Marketing Principles", "BA102", 3, 4),
        ("Accounting I",         "BA103", 4, 5),
        ("Business Law",         "BA104", 3, 4),
        ("Strategic Gestión", "BA105", 3, 4),
    ],
    "ENG": [
        ("Engineering Maths", "ENG101", 4, 6),
        ("Statics",           "ENG102", 3, 4),
        ("Thermodynamics",    "ENG103", 3, 4),
        ("Materials Science", "ENG104", 3, 5),
        ("Fluid Mechanics",   "ENG105", 3, 4),
    ],
}

PERIOD = ("Spring 2026", "SP2026", datetime.date(2026, 2, 1), datetime.date(2026, 6, 30), True)

# (start, end) pairs — non-overlapping so students won't collide
TIME_SLOTS = [
    (datetime.time(8,  0), datetime.time(10, 0)),
    (datetime.time(10, 0), datetime.time(12, 0)),
    (datetime.time(12, 0), datetime.time(14, 0)),
    (datetime.time(14, 0), datetime.time(16, 0)),
    (datetime.time(16, 0), datetime.time(18, 0)),
]
DAYS = [0, 1, 2, 3, 4]  # Mon–Fri

TEACHER_NAMES = [
    ("Carlos",    "García"),
    ("Luis",      "Rodríguez"),
    ("María",     "Martínez"),
    ("Ana",       "López"),
    ("Fernando",  "Hernández"),
    ("Sofía",     "González"),
    ("Javier",    "Pérez"),
    ("Elena",     "Torres"),
    ("Marcos",    "Ramírez"),
    ("Valentina", "Flores"),
]


class Command(BaseCommand):
    help = "Wipe the DB and seed a minimal base (no students) for enrollment testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-wipe",
            action="store_true",
            help="Skip the wipe step and run idempotent upserts only.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if not options["no_wipe"]:
                self._wipe()
            self._seed_users()
            self._seed_academic()
            self._seed_evaluations()
            self._print_summary()
        self.stdout.write(self.style.SUCCESS("\n✓ seed_base completed successfully."))
        self.stdout.write("")
        self.stdout.write("  Credentials:")
        self.stdout.write("    admin    / admin123   (role: admin)")
        self.stdout.write("    mgmt1    / mgmt1123   (role: management)")
        self.stdout.write("    teacher01/ teacher01123 (role: teacher)")
        self.stdout.write("")
        self.stdout.write("  Register a student at /register to test the full enrollment flow.")

    # ------------------------------------------------------------------
    # Wipe
    # ------------------------------------------------------------------
    def _wipe(self):
        self.stdout.write("Wiping database...")

        # Importa aquí para que el comando pueda cargarse antes de las migraciones
        from grades.models import Grade, Evaluation
        from enrollment.models import CareerEnrollment, ClassEnrollment, EnrollmentFee
        from academic.models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule
        from notifications.models import Notification
        from messaging.models import Message
        from users.models import User

        try:
            from admissions.models import AdmissionApplication, AdmissionDocument
            AdmissionDocument.objects.all().delete()
            AdmissionApplication.objects.all().delete()
            self.stdout.write("  Admissions cleared.")
        except Exception:
            pass

        Grade.objects.all().delete()
        Evaluation.objects.all().delete()
        ClassEnrollment.objects.all().delete()
        EnrollmentFee.objects.all().delete()
        CareerEnrollment.objects.all().delete()
        ClassSchedule.objects.all().delete()
        Class.objects.all().delete()
        Classroom.objects.all().delete()
        AcademicPeriod.objects.all().delete()
        Subject.objects.all().delete()
        Career.objects.all().delete()
        Notification.objects.all().delete()
        Message.objects.all().delete()
        User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("  All tables cleared."))

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------
    def _seed_users(self):
        from users.models import User

        self.stdout.write("Seeding users...")

        def upsert(username, email, password, role, first, last):
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(
                    email=email, role=role,
                    first_name=first, last_name=last,
                    is_active=True,
                ),
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            return user

        upsert("admin", "admin@academix.edu", "admin123", "a", "Admin", "System")
        upsert("mgmt1", "mgmt1@academix.edu", "mgmt1123", "m", "Gestión", "Uno")
        upsert("mgmt2", "mgmt2@academix.edu", "mgmt2123", "m", "Gestión", "Dos")

        self._teachers = []
        for i, (first, last) in enumerate(TEACHER_NAMES, start=1):
            uname = f"teacher{i:02d}"
            t = upsert(uname, f"{uname}@academix.edu", f"{uname}123", "t", first, last)
            self._teachers.append(t)

        total = User.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Users: 1 admin, 2 management, {len(self._teachers)} teachers "
            f"— {total} total in DB."
        ))

    # ------------------------------------------------------------------
    # Academic structure
    # ------------------------------------------------------------------
    def _seed_academic(self):
        from academic.models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule

        self.stdout.write("Seeding academic structure...")

        # Careers
        self._careers = {}
        for name, code, duration, spots, desc in CAREERS_DATA:
            career, _ = Career.objects.update_or_create(
                code=code,
                defaults=dict(
                    name=name, description=desc,
                    duration_years=duration, total_spots=spots,
                    is_active=True,
                ),
            )
            self._careers[code] = career
        self.stdout.write(self.style.SUCCESS(f"  Careers: {len(self._careers)}"))

        # Subjects
        self._subjects = {}       # code -> Subject
        self._career_subjects = {}  # career_code -> [Subject]
        for career_code, subj_list in SUBJECTS_DATA.items():
            career = self._careers[career_code]
            self._career_subjects[career_code] = []
            for name, code, credits, hours in subj_list:
                subj, _ = Subject.objects.update_or_create(
                    code=code,
                    defaults=dict(
                        name=name, career=career,
                        credits=credits, hours_per_week=hours,
                        is_active=True,
                    ),
                )
                self._subjects[code] = subj
                self._career_subjects[career_code].append(subj)
        self.stdout.write(self.style.SUCCESS(f"  Subjects: {len(self._subjects)}"))

        # Period
        name, code, start, end, active = PERIOD
        self._period, _ = AcademicPeriod.objects.update_or_create(
            code=code,
            defaults=dict(
                name=name, start_date=start, end_date=end,
                is_active=active,
                enrollment_modification_deadline=end,
            ),
        )
        self.stdout.write(self.style.SUCCESS(f"  Period: {self._period.name} (active={self._period.is_active})"))

        # Classrooms — 4 lecture + 4 lab, capacity 30
        self._classrooms = []
        for i in range(1, 5):
            room, _ = Classroom.objects.update_or_create(
                name=f"Room A{i:02d}",
                building="Main Building",
                defaults=dict(capacity=30, type="lecture"),
            )
            self._classrooms.append(room)
        for i in range(1, 5):
            lab, _ = Classroom.objects.update_or_create(
                name=f"Lab B{i:02d}",
                building="Tech Building",
                defaults=dict(capacity=30, type="lab"),
            )
            self._classrooms.append(lab)
        self.stdout.write(self.style.SUCCESS(f"  Classrooms: {len(self._classrooms)} (capacity 30 each)"))

        # Clases — una por asignatura, distribuye profesores y aulas de forma cíclica
        self._classes = []
        all_subjects_flat = []
        for career_code in [c[1] for c in CAREERS_DATA]:
            all_subjects_flat.extend(self._career_subjects[career_code])

        for idx, subj in enumerate(all_subjects_flat):
            teacher  = self._teachers[idx % len(self._teachers)]
            classroom = self._classrooms[idx % len(self._classrooms)]
            cls, _ = Class.objects.update_or_create(
                subject=subj,
                period=self._period,
                defaults=dict(
                    teacher=teacher,
                    classroom=classroom,
                    max_students=30,
                ),
            )
            self._classes.append(cls)

        self.stdout.write(self.style.SUCCESS(f"  Classes: {len(self._classes)} (max_students=30 each)"))

        # Horarios — 2 por clase, garantizados sin solapes por profesor y día
        # Strategy: assign slots sequentially; each teacher gets at most 1 slot per day-timeslot
        sched_count = 0
        teacher_slots_used: dict = {}  # teacher_id -> set of (day, slot_idx)

        for cls_idx, cls in enumerate(self._classes):
            teacher_id = cls.teacher_id
            if teacher_id not in teacher_slots_used:
                teacher_slots_used[teacher_id] = set()

            slots_assigned = 0
            attempts = 0
            day_offset = cls_idx * 2  # spread across days

            while slots_assigned < 2 and attempts < 50:
                day = DAYS[(day_offset + attempts) % len(DAYS)]
                slot_idx = (cls_idx + attempts // len(DAYS)) % len(TIME_SLOTS)
                key = (day, slot_idx)
                attempts += 1

                if key in teacher_slots_used[teacher_id]:
                    continue

                start_t, end_t = TIME_SLOTS[slot_idx]
                _, created = ClassSchedule.objects.get_or_create(
                    cls=cls,
                    day_of_week=day,
                    start_time=start_t,
                    defaults=dict(end_time=end_t),
                )
                if created:
                    sched_count += 1
                teacher_slots_used[teacher_id].add(key)
                slots_assigned += 1
                day_offset += 1  # next slot uses next day

        self.stdout.write(self.style.SUCCESS(f"  ClassSchedules: {sched_count} created"))

    # ------------------------------------------------------------------
    # Evaluaciones (solo estructura, sin notas)
    # ------------------------------------------------------------------
    def _seed_evaluations(self):
        from grades.models import Evaluation

        self.stdout.write("Seeding evaluations (structure only)...")

        eval_defs = [
            ("Midterm Exam",  "exam",       100),
            ("Assignment 1",  "assignment",  50),
            ("Quiz 1",        "quiz",        30),
        ]

        created = 0
        for cls in self._classes:
            for name, etype, max_score in eval_defs:
                _, c = Evaluation.objects.get_or_create(
                    name=name,
                    cls=cls,
                    defaults=dict(
                        type=etype,
                        max_score=max_score,
                        description=f"{name} for {cls.subject.name}",
                    ),
                )
                if c:
                    created += 1

        self.stdout.write(self.style.SUCCESS(
            f"  Evaluations: {created} created ({len(self._classes) * 3} total expected)"
        ))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _print_summary(self):
        from grades.models import Evaluation
        from enrollment.models import CareerEnrollment, ClassEnrollment
        from academic.models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule
        from users.models import User

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("  BASE SEED SUMMARY")
        self.stdout.write("=" * 50)

        rows = [
            ("Admins",            User.objects.filter(role="a").count()),
            ("Gestión",        User.objects.filter(role="m").count()),
            ("Teachers",          User.objects.filter(role="t").count()),
            ("Students",          User.objects.filter(role="s").count()),
            ("Careers",           Career.objects.count()),
            ("Subjects",          Subject.objects.count()),
            ("Academic Periods",  AcademicPeriod.objects.count()),
            ("Classrooms",        Classroom.objects.count()),
            ("Classes",           Class.objects.count()),
            ("Class Schedules",   ClassSchedule.objects.count()),
            ("Evaluations",       Evaluation.objects.count()),
            ("Career Enrollments",CareerEnrollment.objects.count()),
            ("Class Enrollments", ClassEnrollment.objects.count()),
        ]
        for label, count in rows:
            self.stdout.write(f"  {label:<25} {count:>4}")
        self.stdout.write("=" * 50)
