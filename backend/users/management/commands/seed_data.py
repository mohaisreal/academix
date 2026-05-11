"""
seed_data.py - Large-scale idempotent seed command for Academix.

Scale targets:
  - 1 admin, 2 management, 20 teachers, 500 students
  - 5 careers, 25 subjects (5 per career)
  - 2 academic periods (SP2026 active, FA2025 inactive)
  - 10 classrooms (5 lecture + 5 lab)
  - 50 classes (25 per period), ClassSchedules (2 slots each)
  - 500 CareerEnrollments (1 per student), ~2500 ClassEnrollments (4-6 per student)
  - 150 Evaluations (3 per class), Calificaciones de todos los estudiantes inscritos
  - Notificaciones (bienvenida + calificación) por usuario/estudiante
  - Up to 100 Mensajes (teacher -> student)
"""

import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import User
from academic.models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule
from enrollment.models import CareerEnrollment, ClassEnrollment
from notifications.models import Notification
from messaging.models import Message


# ---------------------------------------------------------------------------
# Name pools (realistic Spanish names)
# ---------------------------------------------------------------------------
MALE_FIRST_NAMES = [
    "Carlos", "Luis", "Diego", "Andrés", "Miguel", "Alejandro", "Juan", "Pablo",
    "Sergio", "Rodrigo", "Fernando", "Javier", "Eduardo", "Raúl", "Marcos",
    "Adrián", "Daniel", "Manuel", "Tomás", "Nicolás",
]
FEMALE_FIRST_NAMES = [
    "María", "Ana", "Sofía", "Valentina", "Camila", "Laura", "Paula", "Isabel",
    "Elena", "Natalia", "Lucía", "Gabriela", "Daniela", "Fernanda", "Verónica",
    "Cristina", "Paola", "Jimena", "Adriana", "Mariana",
]
LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "Hernández", "González",
    "Pérez", "Torres", "Ramírez", "Flores", "Rivera", "Morales", "Castro",
    "Romero", "Vargas", "Jiménez", "Díaz", "Mendoza", "Reyes", "Cruz",
]


def _name_for_index(index):
    """
    Return (first_name, last_name) deterministically from index.
    Even indices -> male names, odd -> female names.
    """
    if index % 2 == 0:
        first = MALE_FIRST_NAMES[index % len(MALE_FIRST_NAMES)]
    else:
        first = FEMALE_FIRST_NAMES[index % len(FEMALE_FIRST_NAMES)]
    last = LAST_NAMES[index % len(LAST_NAMES)]
    return first, last


# ---------------------------------------------------------------------------
# Academic data definitions
# ---------------------------------------------------------------------------
CAREERS_DATA = [
    ("Computer Science",        "CS",  4, "Bachelor's degree in Computer Science and Software Engineering."),
    ("Business Administration",  "BA",  3, "Bachelor's degree in Business Administration and Gestión."),
    ("Engineering",              "ENG", 5, "Bachelor's degree in Mechanical and Civil Engineering."),
    ("Medicine",                 "MED", 6, "Doctor of Medicine degree program."),
    ("Law",                      "LAW", 5, "Bachelor's degree in Law and Legal Studies."),
]

SUBJECTS_DATA = {
    "CS": [
        ("Calculus I",           "CS101", 4, 6),
        ("Programming I",        "CS102", 4, 6),
        ("Data Structures",      "CS103", 3, 4),
        ("Databases",            "CS104", 3, 4),
        ("Computer Networks",    "CS105", 3, 5),
    ],
    "BA": [
        ("Business Economics",   "BA101", 3, 4),
        ("Marketing Principles", "BA102", 3, 4),
        ("Accounting I",         "BA103", 4, 5),
        ("Business Law",         "BA104", 3, 4),
        ("Strategic Gestión", "BA105", 3, 4),
    ],
    "ENG": [
        ("Engineering Maths",    "ENG101", 4, 6),
        ("Statics",              "ENG102", 3, 4),
        ("Thermodynamics",       "ENG103", 3, 4),
        ("Ciencia de materiales",    "ENG104", 3, 5),
        ("Fluid Mechanics",      "ENG105", 3, 4),
    ],
    "MED": [
        ("Human Anatomy",        "MED101", 5, 8),
        ("Biochemistry",         "MED102", 4, 6),
        ("Physiology",           "MED103", 4, 6),
        ("Microbiology",         "MED104", 3, 5),
        ("Pharmacology I",       "MED105", 3, 5),
    ],
    "LAW": [
        ("Civil Law",            "LAW101", 4, 5),
        ("Constitutional Law",   "LAW102", 4, 5),
        ("Criminal Law",         "LAW103", 4, 5),
        ("Commercial Law",       "LAW104", 3, 4),
        ("Administrative Law",   "LAW105", 3, 4),
    ],
}

PERIOD_DEFS = [
    ("Spring 2026", "SP2026", datetime.date(2026, 2, 1),  datetime.date(2026, 6, 30),  True),
    ("Fall 2025",   "FA2025", datetime.date(2025, 9, 1),  datetime.date(2026, 1, 31),  False),
]

# Fixed time slots: (start_time, end_time)
TIME_SLOTS = [
    (datetime.time(8, 0),  datetime.time(10, 0)),
    (datetime.time(10, 0), datetime.time(12, 0)),
    (datetime.time(12, 0), datetime.time(14, 0)),
    (datetime.time(14, 0), datetime.time(16, 0)),
    (datetime.time(16, 0), datetime.time(18, 0)),
]

# Days 0=Monday..4=Friday
DAYS = [0, 1, 2, 3, 4]


class Command(BaseCommand):
    help = "Seed the database with large-scale realistic test data (idempotent, ~500 students)."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_users()
            self._seed_academic()
            self._seed_enrollments()
            self._seed_grades()
            self._seed_notifications()
            self._seed_messages()
            self._print_summary()
        self.stdout.write(self.style.SUCCESS("\nSeed completed exitosaly."))

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------
    def _get_or_create_user(self, username, email, password, role, first_name, last_name):
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                first_name=first_name,
                last_name=last_name,
            )
            return user, True
        return user, False

    def _seed_users(self):
        self.stdout.write("Seeding users...")
        created_count = 0

        # Admin
        _, c = self._get_or_create_user(
            "admin", "admin@academix.edu", "admin123", "a", "Admin", "System"
        )
        if c:
            created_count += 1

        # Gestión
        for i, uname in enumerate(["mgmt1", "mgmt2"]):
            first, last = _name_for_index(i)
            _, c = self._get_or_create_user(
                uname, f"{uname}@academix.edu", f"{uname}123", "m", first, last
            )
            if c:
                created_count += 1

        # Profesores: teacher01..teacher20
        self._teachers = []
        for i in range(1, 21):
            uname = f"teacher{i:02d}"
            first, last = _name_for_index(i - 1)
            user, c = self._get_or_create_user(
                uname, f"{uname}@academix.edu", f"{uname}123", "t", first, last
            )
            if c:
                created_count += 1
            self._teachers.append(user)

        # Estudiantes: student001..student500
        self._students = []
        for i in range(1, 501):
            uname = f"student{i:03d}"
            first, last = _name_for_index(i - 1)
            user, c = self._get_or_create_user(
                uname, f"{uname}@academix.edu", f"{uname}123", "s", first, last
            )
            if c:
                created_count += 1
            self._students.append(user)

        total = 1 + 2 + 20 + 500
        self.stdout.write(self.style.SUCCESS(
            f"  Usuarios: {created_count} creados, {total - created_count} ya existían "
            f"(total target: {total})."
        ))

    # ------------------------------------------------------------------
    # Academic structure
    # ------------------------------------------------------------------
    def _seed_academic(self):
        self.stdout.write("Seeding academic structure...")

        # --- Careers ---
        self._careers = {}
        for name, code, duration, desc in CAREERS_DATA:
            career, _ = Career.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": desc,
                    "duration_years": duration,
                    "is_active": True,
                },
            )
            self._careers[code] = career
        self.stdout.write(self.style.SUCCESS(f"  Careers: {len(self._careers)} seeded."))

        # --- Subjects ---
        self._subjects = {}  # code -> Subject
        self._career_subjects = {}  # career_code -> [Subject, ...]
        for career_code, subj_list in SUBJECTS_DATA.items():
            career = self._careers[career_code]
            self._career_subjects[career_code] = []
            for name, code, credits, hours in subj_list:
                subj, _ = Subject.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "career": career,
                        "credits": credits,
                        "hours_per_week": hours,
                        "is_active": True,
                    },
                )
                self._subjects[code] = subj
                self._career_subjects[career_code].append(subj)
        self.stdout.write(self.style.SUCCESS(f"  Subjects: {len(self._subjects)} seeded."))

        # --- Academic periods ---
        self._periods = {}
        for name, code, start, end, active in PERIOD_DEFS:
            period, _ = AcademicPeriod.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "start_date": start,
                    "end_date": end,
                    "is_active": active,
                },
            )
            self._periods[code] = period
        self.stdout.write(self.style.SUCCESS(f"  AcademicPeriods: {len(self._periods)} seeded."))

        # --- Classrooms ---
        # Aulas 101-105 en el edificio principal (teoría, capacidad 40)
        # Laboratorios 201-205 en el edificio técnico (laboratorio, capacidad 25)
        self._classrooms = []
        for i in range(1, 6):
            room, _ = Classroom.objects.get_or_create(
                name=f"Room 10{i}",
                building="Main Building",
                defaults={"capacity": 40, "type": "lecture"},
            )
            self._classrooms.append(room)
        for i in range(1, 6):
            lab, _ = Classroom.objects.get_or_create(
                name=f"Lab 20{i}",
                building="Tech Building",
                defaults={"capacity": 25, "type": "lab"},
            )
            self._classrooms.append(lab)
        self.stdout.write(self.style.SUCCESS(f"  Classrooms: {len(self._classrooms)} seeded."))

        # --- Clases: 25 por periodo (una por asignatura y periodo) ---
        # self._classes[period_code] = [Class, ...] ordenadas por índice de asignatura
        self._classes = {}
        all_subjects_ordered = []
        for _, career_code, *_ in CAREERS_DATA:
            all_subjects_ordered.extend(self._career_subjects[career_code])

        teacher_cycle = 0
        classroom_cycle = 0

        for period_code, period in self._periods.items():
            period_classes = []
            for subj_idx, subj in enumerate(all_subjects_ordered):
                teacher = self._teachers[teacher_cycle % len(self._teachers)]
                classroom = self._classrooms[classroom_cycle % len(self._classrooms)]
                max_students = classroom.capacity

                cls, _ = Class.objects.get_or_create(
                    subject=subj,
                    period=period,
                    defaults={
                        "teacher": teacher,
                        "classroom": classroom,
                        "max_students": max_students,
                    },
                )
                period_classes.append(cls)
                teacher_cycle += 1
                classroom_cycle += 1

            self._classes[period_code] = period_classes

        total_classes = sum(len(v) for v in self._classes.values())
        self.stdout.write(self.style.SUCCESS(f"  Classes: {total_classes} seeded."))

        # --- ClassSchedules: 2 franjas por clase ---
        sched_created = 0
        for period_code, period_classes in self._classes.items():
            for cls_idx, cls in enumerate(period_classes):
                # First slot
                slot1_idx = cls_idx % len(TIME_SLOTS)
                day1 = DAYS[cls_idx % len(DAYS)]
                start1, end1 = TIME_SLOTS[slot1_idx]
                _, c = ClassSchedule.objects.get_or_create(
                    cls=cls,
                    day_of_week=day1,
                    start_time=start1,
                    defaults={"end_time": end1},
                )
                if c:
                    sched_created += 1

                # Second slot (offset by 2)
                slot2_idx = (cls_idx + 2) % len(TIME_SLOTS)
                day2 = DAYS[(cls_idx + 2) % len(DAYS)]
                start2, end2 = TIME_SLOTS[slot2_idx]
                # Evita duplicados (misma clase + día + start_time)
                if day2 != day1 or start2 != start1:
                    _, c = ClassSchedule.objects.get_or_create(
                        cls=cls,
                        day_of_week=day2,
                        start_time=start2,
                        defaults={"end_time": end2},
                    )
                    if c:
                        sched_created += 1

        self.stdout.write(self.style.SUCCESS(f"  ClassSchedules: {sched_created} created (2 per class)."))

    # ------------------------------------------------------------------
    # Enrollments
    # ------------------------------------------------------------------
    def _seed_enrollments(self):
        self.stdout.write("Seeding enrollments...")

        period_sp = self._periods["SP2026"]
        period_fa = self._periods["FA2025"]
        career_codes = [c[1] for c in CAREERS_DATA]  # ["CS","BA","ENG","MED","LAW"]

        # Construye el mapa titulación -> clases para ambos periodos
        all_subjects_ordered = []
        for _, career_code, *_ in CAREERS_DATA:
            all_subjects_ordered.extend(self._career_subjects[career_code])

        # Mapea asignatura -> clase por periodo
        subj_to_class = {}  # (subj_id, period_code) -> Class
        for period_code, period_classes in self._classes.items():
            for cls in period_classes:
                subj_to_class[(cls.subject_id, period_code)] = cls

        # Titulación -> lista de asignaturas
        career_subj_map = {code: self._career_subjects[code] for code in career_codes}

        # --- CareerEnrollments ---
        # 500 estudiantes, 100 por titulación
        # Periodo: SP2026 para estudiantes 0-399 (índice), FA2025 para 400-499
        # Estado: 80% activo, 10% completado, 10% pendiente
        ce_to_create = []
        ce_existing = 0

        def career_status(student_idx):
            r = student_idx % 10
            if r < 8:
                return "active"
            elif r == 8:
                return "completed"
            else:
                return "pending"

        for i, student in enumerate(self._students):
            career_code = career_codes[i % len(career_codes)]  # distribute evenly, 100 each
            career = self._careers[career_code]
            period = period_sp if i < 400 else period_fa
            status = career_status(i)

            # Check existence
            exists = CareerEnrollment.objects.filter(
                student=student, career=career, period=period
            ).exists()
            if not exists:
                ce_to_create.append(CareerEnrollment(
                    student=student,
                    career=career,
                    period=period,
                    status=status,
                ))
            else:
                ce_existing += 1

        if ce_to_create:
            CareerEnrollment.objects.bulk_create(ce_to_create, ignore_conflicts=True)

        ce_total = CareerEnrollment.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  CareerEnrollments: {len(ce_to_create)} new, {ce_existing} existed "
            f"(total in DB: {ce_total})."
        ))

        # --- ClassEnrollments ---
        # Cada estudiante matriculado en 4-6 clases de las asignaturas de su titulación
        # Los estudiantes de SP2026 usan clases de SP2026; los de FA2025 usan clases de FA2025
        # Estado: 85% matriculado, 10% dado de baja, 5% en lista de espera
        def class_enroll_status(student_idx, cls_slot):
            r = (student_idx * 7 + cls_slot) % 20
            if r < 17:
                return "enrolled"
            elif r < 19:
                return "dropped"
            else:
                return "waitlisted"

        # Recoge pares existentes (student_id, cls_id) para omitirlos
        existing_class_enroll_set = set(
            ClassEnrollment.objects.values_list("student_id", "cls_id")
        )

        new_class_enrollments = []
        for i, student in enumerate(self._students):
            career_code = career_codes[i % len(career_codes)]
            period_code = "SP2026" if i < 400 else "FA2025"
            subjects_for_career = career_subj_map[career_code]  # 5 subjects

            # Número de clases: 4, 5 o 6 de forma cíclica
            num_classes = 4 + (i % 3)  # 4, 5, 6, 4, 5, 6, ...
            # Toma hasta num_classes de las 5 asignaturas disponibles
            selected_subjects = subjects_for_career[:num_classes]

            for slot, subj in enumerate(selected_subjects):
                cls = subj_to_class.get((subj.id, period_code))
                if cls is None:
                    continue
                if (student.id, cls.id) not in existing_class_enroll_set:
                    status = class_enroll_status(i, slot)
                    new_class_enrollments.append(ClassEnrollment(
                        student=student,
                        cls=cls,
                        status=status,
                    ))
                    existing_class_enroll_set.add((student.id, cls.id))

        if new_class_enrollments:
            # bulk_create en lotes de 1000
            batch_size = 1000
            for start in range(0, len(new_class_enrollments), batch_size):
                ClassEnrollment.objects.bulk_create(
                    new_class_enrollments[start:start + batch_size],
                    ignore_conflicts=True,
                )

        ce2_total = ClassEnrollment.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  ClassEnrollments: {len(new_class_enrollments)} new rows attempted "
            f"(total in DB: {ce2_total})."
        ))

        # Guarda matrículas de clase activas para sembrar notas
        self._enrolled_class_enrollments = list(
            ClassEnrollment.objects.filter(status="enrolled").select_related(
                "student", "cls", "cls__teacher", "cls__subject"
            )
        )

    # ------------------------------------------------------------------
    # Evaluations + Calificaciones
    # ------------------------------------------------------------------
    def _seed_grades(self):
        self.stdout.write("Seeding evaluations and grades...")

        # --- Evaluaciones: 3 por clase ---
        # Key: (name, cls_id)
        eval_defs = [
            ("Midterm Exam",    "exam",       100),
            ("Assignment 1",    "assignment", 50),
            ("Quiz 1",          "quiz",       30),
        ]

        # Recoge todas las clases
        all_classes = []
        for period_classes in self._classes.values():
            all_classes.extend(period_classes)

        # Construye búsqueda de evaluaciones: cls_id -> {type -> Evaluation}
        self._evaluations = {}  # cls_id -> [Evaluation, Evaluation, Evaluation]

        evals_to_create = []

        # Fetch existing evaluations keyed by (name, cls_id)
        from grades.models import Evaluation as EvalModel
        existing_eval_map = {}
        for ev in EvalModel.objects.filter(cls__in=all_classes):
            existing_eval_map[(ev.name, ev.cls_id)] = ev

        for cls in all_classes:
            cls_evals = []
            for eval_name, eval_type, max_score in eval_defs:
                key = (eval_name, cls.id)
                if key in existing_eval_map:
                    cls_evals.append(existing_eval_map[key])
                else:
                    ev = EvalModel(
                        name=eval_name,
                        cls=cls,
                        type=eval_type,
                        max_score=max_score,
                        description=f"{eval_name} for {cls.subject.name}",
                    )
                    evals_to_create.append(ev)
                    cls_evals.append(ev)  # placeholder; id set after bulk_create
            self._evaluations[cls.id] = cls_evals

        if evals_to_create:
            EvalModel.objects.bulk_create(evals_to_create, ignore_conflicts=True)
            # Vuelve a consultar para obtener los ID de evaluaciones recién creadas
            for ev in EvalModel.objects.filter(cls__in=all_classes):
                existing_eval_map[(ev.name, ev.cls_id)] = ev
            # Reconstruye con objetos reales
            for cls in all_classes:
                cls_evals = []
                for eval_name, _, _ in eval_defs:
                    key = (eval_name, cls.id)
                    if key in existing_eval_map:
                        cls_evals.append(existing_eval_map[key])
                self._evaluations[cls.id] = cls_evals

        eval_total = EvalModel.objects.filter(cls__in=all_classes).count()
        self.stdout.write(self.style.SUCCESS(
            f"  Evaluations: {len(evals_to_create)} new, total {eval_total}."
        ))

        # --- Calificaciones ---
        # Para cada ClassEnrollment con status=enrolled, califica las 3 evaluaciones
        # Puntuación: distribución normal centrada en el 70% de max_score, desv.=15%
        # Usa el profesor de la clase como graded_by

        from grades.models import Grade as GradeModel

        # Fetch existing grades: set of (student_id, evaluation_id)
        existing_grades_set = set(
            GradeModel.objects.values_list("student_id", "evaluation_id")
        )

        rng = random.Random(42)  # semilla determinista para reproducibilidad

        new_grades = []
        for enrollment in self._enrolled_class_enrollments:
            cls = enrollment.cls
            student = enrollment.student
            teacher = cls.teacher
            evals = self._evaluations.get(cls.id, [])

            for ev in evals:
                if ev.id is None:
                    continue  # safety check
                if (student.id, ev.id) in existing_grades_set:
                    continue
                max_s = float(ev.max_score)
                mean = 0.70 * max_s
                std = 0.15 * max_s
                raw = rng.gauss(mean, std)
                score = round(max(0.0, min(max_s, raw)), 2)
                new_grades.append(GradeModel(
                    student=student,
                    evaluation=ev,
                    score=score,
                    graded_by=teacher,
                    feedback="",
                ))
                existing_grades_set.add((student.id, ev.id))

        if new_grades:
            batch_size = 2000
            for start in range(0, len(new_grades), batch_size):
                GradeModel.objects.bulk_create(
                    new_grades[start:start + batch_size],
                    ignore_conflicts=True,
                )

        grade_total = GradeModel.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Calificaciones: {len(new_grades)} new rows attempted (total in DB: {grade_total})."
        ))

    # ------------------------------------------------------------------
    # Notificaciones
    # ------------------------------------------------------------------
    def _seed_notifications(self):
        self.stdout.write("Seeding notifications...")

        all_users = list(User.objects.all())

        # Notificaciones de bienvenida: usa (user_id, title) como clave de unicidad
        existing_welcome = set(
            Notification.objects.filter(title="Bienvenido a Academix").values_list("user_id", flat=True)
        )

        welcome_notifs = []
        for user in all_users:
            if user.id not in existing_welcome:
                welcome_notifs.append(Notification(
                    user=user,
                    title="Bienvenido a Academix",
                    message=(
                        f"Hello {user.first_name or user.username}, welcome to the Academix "
                        "academic management system. We hope you have a great experience."
                    ),
                    type="info",
                    is_read=False,
                ))

        if welcome_notifs:
            Notification.objects.bulk_create(welcome_notifs, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f"  Notificaciones de bienvenida: {len(welcome_notifs)} nuevas."
        ))

        # Notificaciones de notas: 1 por estudiante y clase matriculada
        # "Notas disponibles para [nombre de asignatura]", type=info, is_read: 50% True
        # Clave por (user_id, title); title incluye el nombre de la asignatura
        rng = random.Random(99)

        existing_grade_notif_pairs = set(
            Notification.objects.filter(
                user__role="s",
                title__startswith="Calificaciones disponibles para",
            ).values_list("user_id", "title")
        )

        grade_notifs = []
        for enrollment in self._enrolled_class_enrollments:
            student = enrollment.student
            subject_name = enrollment.cls.subject.name
            title = f"Calificaciones disponibles para {subject_name}"
            if (student.id, title) not in existing_grade_notif_pairs:
                is_read = rng.random() < 0.5
                grade_notifs.append(Notification(
                    user=student,
                    title=title,
                    message=f"Las calificaciones ya están disponibles para {subject_name}. Inicia sesión para revisar tus resultados.",
                    type="info",
                    is_read=is_read,
                ))
                existing_grade_notif_pairs.add((student.id, title))

        if grade_notifs:
            batch_size = 2000
            for start in range(0, len(grade_notifs), batch_size):
                Notification.objects.bulk_create(
                    grade_notifs[start:start + batch_size],
                    ignore_conflicts=True,
                )

        notif_total = Notification.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Notificaciones de calificaciones: {len(grade_notifs)} nuevas (total en BD: {notif_total})."
        ))

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------
    def _seed_messages(self):
        self.stdout.write("Seeding messages (capped at 100)...")

        # Construye lista ordenada de pares (profesor, estudiante), límite 100
        # También se necesita el nombre de la asignatura para el cuerpo del mensaje
        # Construye un mapa: (teacher_id, student_id) -> subject_name (primero encontrado)
        pair_subject = {}
        for enrollment in self._enrolled_class_enrollments:
            teacher = enrollment.cls.teacher
            if teacher is None:
                continue
            key = (teacher.id, enrollment.student.id)
            if key not in pair_subject:
                pair_subject[key] = enrollment.cls.subject.name

        # Orden determinista: ordenar por username del profesor y luego username del estudiante
        all_pairs = sorted(pair_subject.keys())[:100]

        # Obtén mensajes existentes por (sender_id, recipient_id, subject)
        msg_subject_str = "Actualización de curso"
        existing_msg_pairs = set(
            Message.objects.filter(subject=msg_subject_str).values_list("sender_id", "recipient_id")
        )

        # Construye mapa ID de usuario -> objeto User por eficiencia
        user_ids_needed = set()
        for t_id, s_id in all_pairs:
            user_ids_needed.add(t_id)
            user_ids_needed.add(s_id)
        user_map = {u.id: u for u in User.objects.filter(id__in=user_ids_needed)}

        new_messages = []
        for teacher_id, student_id in all_pairs:
            if (teacher_id, student_id) in existing_msg_pairs:
                continue
            teacher = user_map.get(teacher_id)
            student = user_map.get(student_id)
            if teacher is None or student is None:
                continue
            subj_name = pair_subject[(teacher_id, student_id)]
            new_messages.append(Message(
                sender=teacher,
                recipient=student,
                subject=msg_subject_str,
                body=f"Please check the latest materials for {subj_name}.",
                is_read=False,
            ))

        if new_messages:
            Message.objects.bulk_create(new_messages, ignore_conflicts=True)

        msg_total = Message.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Mensajes: {len(new_messages)} nuevos (total en BD: {msg_total})."
        ))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _print_summary(self):
        from grades.models import Evaluation as EvalModel, Grade as GradeModel

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("  SEED SUMMARY")
        self.stdout.write("=" * 60)

        rows = [
            ("Usuarios",             User.objects.count()),
            ("  - admin",         User.objects.filter(role="a").count()),
            ("  - management",    User.objects.filter(role="m").count()),
            ("  - teachers",      User.objects.filter(role="t").count()),
            ("  - students",      User.objects.filter(role="s").count()),
            ("Careers",           Career.objects.count()),
            ("Asignaturas",          Subject.objects.count()),
            ("AcademicPeriods",   AcademicPeriod.objects.count()),
            ("Classrooms",        Classroom.objects.count()),
            ("Classes",           Class.objects.count()),
            ("ClassSchedules",    ClassSchedule.objects.count()),
            ("CareerEnrollments", CareerEnrollment.objects.count()),
            ("ClassEnrollments",  ClassEnrollment.objects.count()),
            ("Evaluations",       EvalModel.objects.count()),
            ("Calificaciones",            GradeModel.objects.count()),
            ("Notificaciones",     Notification.objects.count()),
            ("Mensajes",          Message.objects.count()),
        ]

        for label, count in rows:
            self.stdout.write(f"  {label:<25} {count:>6}")

        self.stdout.write("=" * 60)
