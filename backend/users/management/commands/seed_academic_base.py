from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academic.models import AcademicPeriod, Career, Classroom, Department, Subject
from admissions.models import AdmissionApplication, AdmissionPreference
from users.models import User

ACADEMIC_CATALOG = [
    {"career": {"code": "ING-SIS", "name": "Ingeniería en Sistemas"}, "subjects": [
        {"code": "IS-ALG", "name": "Álgebra Lineal", "department": "DEP-MAT"},
        {"code": "IS-PRO", "name": "Programación I", "department": "DEP-INF"},
        {"code": "IS-BDD", "name": "Bases de Datos", "department": "DEP-INF"},
        {"code": "IS-SO", "name": "Sistemas Operativos", "department": "DEP-INF"},
        {"code": "IS-RED", "name": "Redes de Computadores", "department": "DEP-TEL"},
        {"code": "IS-ING", "name": "Ingeniería de Software", "department": "DEP-INF"},
    ]},
    {"career": {"code": "MED", "name": "Medicina"}, "subjects": [
        {"code": "MED-ANA", "name": "Anatomía Humana", "department": "DEP-SAL"},
        {"code": "MED-FIS", "name": "Fisiología", "department": "DEP-SAL"},
        {"code": "MED-MIC", "name": "Microbiología", "department": "DEP-SAL"},
        {"code": "MED-FAR", "name": "Farmacología", "department": "DEP-SAL"},
        {"code": "MED-CLI", "name": "Medicina Clínica", "department": "DEP-SAL"},
        {"code": "MED-SAL", "name": "Salud Pública", "department": "DEP-SAL"},
    ]},
    {"career": {"code": "ADE", "name": "Administración y Dirección de Empresas"}, "subjects": [
        {"code": "ADE-MAT", "name": "Matemática Financiera", "department": "DEP-ECO"},
        {"code": "ADE-CON", "name": "Contabilidad General", "department": "DEP-ECO"},
        {"code": "ADE-MKT", "name": "Marketing Estratégico", "department": "DEP-ADM"},
        {"code": "ADE-RHH", "name": "Dirección de Recursos Humanos", "department": "DEP-ADM"},
        {"code": "ADE-DER", "name": "Derecho Mercantil", "department": "DEP-ECO"},
        {"code": "ADE-OPR", "name": "Gestión de Operaciones", "department": "DEP-ADM"},
    ]},
    {"career": {"code": "ARQ", "name": "Arquitectura"}, "subjects": [
        {"code": "ARQ-DIB", "name": "Dibujo Arquitectónico", "department": "DEP-ARQ"},
        {"code": "ARQ-MAT", "name": "Materiales de Construcción", "department": "DEP-ARQ"},
        {"code": "ARQ-EST", "name": "Estructuras I", "department": "DEP-ARQ"},
        {"code": "ARQ-URB", "name": "Urbanismo", "department": "DEP-ARQ"},
        {"code": "ARQ-HIS", "name": "Historia de la Arquitectura", "department": "DEP-ARQ"},
        {"code": "ARQ-PRO", "name": "Proyectos Arquitectónicos", "department": "DEP-ARQ"},
    ]},
    {"career": {"code": "PSI", "name": "Psicología"}, "subjects": [
        {"code": "PSI-GEN", "name": "Psicología General", "department": "DEP-PSI"},
        {"code": "PSI-DES", "name": "Psicología del Desarrollo", "department": "DEP-PSI"},
        {"code": "PSI-SOC", "name": "Psicología Social", "department": "DEP-PSI"},
        {"code": "PSI-EVA", "name": "Evaluación Psicológica", "department": "DEP-PSI"},
        {"code": "PSI-CLI", "name": "Psicología Clínica", "department": "DEP-PSI"},
        {"code": "PSI-NEU", "name": "Neuropsicología", "department": "DEP-PSI"},
    ]},
]

DEPARTMENTS = [
    ("DEP-INF", "Departamento de Informática"),
    ("DEP-MAT", "Departamento de Matemáticas"),
    ("DEP-TEL", "Departamento de Telecomunicaciones"),
    ("DEP-SAL", "Departamento de Ciencias de la Salud"),
    ("DEP-ADM", "Departamento de Administración y Gestión"),
    ("DEP-ECO", "Departamento de Economía y Derecho"),
    ("DEP-ARQ", "Departamento de Arquitectura y Urbanismo"),
    ("DEP-PSI", "Departamento de Psicología"),
]

TEACHER_CATALOG = [
    ("prof_ana_torres", "ana.torres", "Ana", "Torres"),
    ("prof_luis_ramirez", "luis.ramirez", "Luis", "Ramírez"),
    ("prof_carla_mendez", "carla.mendez", "Carla", "Méndez"),
    ("prof_diego_santos", "diego.santos", "Diego", "Santos"),
    ("prof_maria_vargas", "maria.vargas", "María", "Vargas"),
    ("prof_pablo_ibarra", "pablo.ibarra", "Pablo", "Ibarra"),
    ("prof_laura_rojas", "laura.rojas", "Laura", "Rojas"),
    ("prof_jorge_leon", "jorge.leon", "Jorge", "León"),
    ("prof_elena_ruiz", "elena.ruiz", "Elena", "Ruiz"),
    ("prof_felipe_navarro", "felipe.navarro", "Felipe", "Navarro"),
    ("prof_sofia_arias", "sofia.arias", "Sofía", "Arias"),
    ("prof_ricardo_vega", "ricardo.vega", "Ricardo", "Vega"),
]

CLASSROOMS = 10
STUDENTS = 60
ADMISSION_APPLICANTS = 12
SEED_TIME_SLOTS = [
    (day, start, end)
    for day in range(5)
    for start, end in [
        ("08:00", "09:00"),
        ("09:00", "10:00"),
        ("10:00", "11:00"),
        ("11:00", "12:00"),
        ("14:00", "15:00"),
        ("15:00", "16:00"),
    ]
]


class Command(BaseCommand):
    help = "Regenera dataset académico realista y suficiente para generación de horarios base, con DNIs NUMIDIF<N> solo para estudiantes."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._clean_target_scope()
            careers = self._seed_careers()
            self._seed_students()
            teachers = self._seed_teachers()
            departments = self._seed_departments(teachers)
            self._seed_subjects(careers, departments)
            self._seed_classrooms()
            period = self._seed_submitted_admission_applications()
            self._seed_time_slots(period)
            self._validate_distribution()
            self._validate_timetable_readiness(period)

        self.stdout.write(self.style.SUCCESS("Seed académico base completado."))

    def _clean_target_scope(self):
        User.objects.filter(role__in=["s", "t"]).delete()
        Subject.objects.all().delete()
        Department.objects.all().delete()
        Classroom.objects.all().delete()
        AcademicPeriod.objects.filter(code="SEED-AP-01").delete()
        Career.objects.all().delete()

    def _seed_careers(self):
        careers = []
        for row in ACADEMIC_CATALOG:
            careers.append(Career.objects.create(
                code=row["career"]["code"],
                name=row["career"]["name"],
                description=f"Plan académico base de {row['career']['name']}.",
                duration_years=4,
                total_spots=120,
                is_active=True,
            ))
        return careers

    def _seed_students(self):
        for i in range(1, STUDENTS + 1):
            username = f"estudiante{i}"
            User.objects.create_user(
                username=username,
                password="academix123",
                role="s",
                dni=self._student_dni(i),
                email=f"{username}@academix.local",
                first_name="Estudiante",
                last_name=str(i),
                is_active=True,
            )

    def _student_dni(self, index):
        return f"NUMIDIF{index}"

    def _seed_teachers(self):
        teachers = []
        for username, email_local, first_name, last_name in TEACHER_CATALOG:
            teacher = User.objects.create_user(
                username=username,
                password="academix123",
                role="t",
                email=f"{email_local}@academix.local",
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            teachers.append(teacher)
        return teachers

    def _seed_departments(self, teachers):
        departments = []
        for index, (code, name) in enumerate(DEPARTMENTS):
            departments.append(Department.objects.create(
                code=code,
                name=name,
                description=f"Área académica de {name}.",
                teacher=teachers[index] if index < len(teachers) else None,
                is_active=True,
            ))
        return departments

    def _seed_subjects(self, careers, departments):
        career_by_code = {c.code: c for c in careers}
        department_by_code = {d.code: d for d in departments}
        for row in ACADEMIC_CATALOG:
            career = career_by_code[row["career"]["code"]]
            for item in row["subjects"]:
                Subject.objects.create(
                    code=item["code"],
                    name=item["name"],
                    career=career,
                    department=department_by_code[item["department"]],
                    credits=6,
                    hours_per_week=4,
                    subject_type="obligatoria",
                    is_active=True,
                ).careers.add(career)

    def _seed_classrooms(self):
        for i in range(1, CLASSROOMS + 1):
            Classroom.objects.create(name=f"Aula {i}", building="Edificio Principal", capacity=35 + i, type="lecture")

    def _seed_submitted_admission_applications(self):
        active_period = AcademicPeriod.objects.filter(is_active=True).order_by("start_date").first()
        if active_period is None:
            active_period = AcademicPeriod.objects.create(
                name="Periodo Académico Seed",
                code="SEED-AP-01",
                start_date="2026-01-10",
                end_date="2026-06-20",
                is_active=True,
            )
        submitted_students = User.objects.filter(role="s").order_by("id")[:ADMISSION_APPLICANTS]
        careers = list(Career.objects.order_by("code"))
        submitted_at = timezone.now()
        for index, student in enumerate(submitted_students):
            target_career = careers[index % len(careers)]
            application = AdmissionApplication.objects.create(
                student=student,
                academic_period=active_period,
                access_route="evau",
                bachillerato_grade=8.500,
                evau_obligatory_grade=8.000,
                evau_voluntary_subjects=[{"subject": "Matemáticas II", "grade": 9.500}, {"subject": "Física", "grade": 9.000}],
                admission_score=10.100,
                assigned_career=target_career,
                assigned_preference_order=1,
                status="submitted",
                submission_date=submitted_at,
            )
            AdmissionPreference.objects.create(application=application, career=target_career, preference_order=1, status="pending")
        return active_period

    def _seed_time_slots(self, period):
        period.time_slots.all().delete()
        for day, start_time, end_time in SEED_TIME_SLOTS:
            period.time_slots.create(day_of_week=day, start_time=start_time, end_time=end_time)

    def _validate_distribution(self):
        if Subject.objects.filter(careers__isnull=True).exists():
            raise CommandError("Se detectaron asignaturas sin carrera asociada.")
        if Career.objects.filter(subjects__isnull=True).exists():
            raise CommandError("Se detectaron carreras sin asignaturas.")

    def _validate_timetable_readiness(self, period):
        active_subjects = Subject.objects.filter(is_active=True)
        if active_subjects.filter(department__isnull=True).exists():
            raise CommandError("Readiness inválido: hay asignaturas sin departamento.")
        if Department.objects.filter(is_active=True, teacher__isnull=True).exists():
            raise CommandError("Readiness inválido: hay departamentos sin docente responsable.")

        subject_count = active_subjects.count()
        classroom_count = Classroom.objects.count()
        slot_count = period.time_slots.count()
        teacher_count = Department.objects.filter(is_active=True).count()

        if classroom_count == 0:
            raise CommandError("Readiness inválido: no hay aulas disponibles.")
        if slot_count < subject_count:
            raise CommandError("Readiness inválido: slots insuficientes para asignaturas activas.")
        if slot_count * teacher_count < subject_count:
            raise CommandError("Readiness inválido: capacidad docente insuficiente para clases base.")
        if slot_count * classroom_count < subject_count:
            raise CommandError("Readiness inválido: capacidad de aulas insuficiente para clases base.")
