from django.test import TestCase
from django.db import IntegrityError
from rest_framework.test import APIClient

from users.models import User
from academic.models import Classroom, Career, Subject, Department


class ClassroomPaginationFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='mgr_pag', email='mgr_pag@test.com', password='testpass123', role='m', is_active=True)
        self.client.force_authenticate(user=self.user)
        for idx in range(22):
            Classroom.objects.create(name=f'Aula T{idx}', building='A', capacity=30, type='lecture')
        Classroom.objects.create(name='Lab 1', building='B', capacity=20, type='lab')

    def test_classrooms_can_filter_by_type_before_pagination(self):
        response = self.client.get('/api/academic/classrooms/?type=lab&page=1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['type'], 'lab')


class DepartmentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            username='mgr_dept',
            email='mgr_dept@test.com',
            password='testpass123',
            role='m',
            is_active=True,
        )
        self.teacher = User.objects.create_user(
            username='teach_dept',
            email='teach_dept@test.com',
            password='testpass123',
            role='t',
            is_active=True,
            first_name='Ada',
            last_name='Lovelace',
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING')
        self.client.force_authenticate(user=self.manager)

    def test_departments_crud_and_list(self):
        create_response = self.client.post('/api/academic/departments/', {
            'name': 'Matemática',
            'code': 'MAT',
            'description': 'Departamento de matemáticas',
            'teacher': self.teacher.id,
            'is_active': True,
        }, format='json')

        self.assertEqual(create_response.status_code, 201)
        department_id = create_response.json()['id']

        Subject.objects.create(
            name='Álgebra',
            code='ALG1',
            career=self.career,
            department_id=department_id,
            is_active=True,
        )

        list_response = self.client.get('/api/academic/departments/')
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['teacher_name'], 'Ada Lovelace')
        self.assertEqual(payload['results'][0]['subjects_count'], 1)

        update_response = self.client.patch(f'/api/academic/departments/{department_id}/', {
            'description': 'Departamento de matemática aplicada',
        }, format='json')
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()['description'], 'Departamento de matemática aplicada')

        delete_response = self.client.delete(f'/api/academic/departments/{department_id}/')
        self.assertEqual(delete_response.status_code, 204)

    def test_department_teacher_is_unique_by_database_constraint(self):
        Department.objects.create(name='Matemática', code='MAT', teacher=self.teacher)

        with self.assertRaises(IntegrityError):
            Department.objects.create(name='Física', code='FIS', teacher=self.teacher)

    def test_subject_serializer_includes_department_fields(self):
        department = Department.objects.create(name='Matemática', code='MAT', teacher=self.teacher)
        subject = Subject.objects.create(
            name='Álgebra',
            code='ALG2',
            career=self.career,
            department=department,
            is_active=True,
        )

        response = self.client.get(f'/api/academic/subjects/{subject.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['department'], department.id)
        self.assertEqual(data['department_name'], 'Matemática')
        self.assertEqual(data['department_teacher_name'], 'Ada Lovelace')

    def test_subject_patch_can_change_and_clear_department(self):
        first_department = Department.objects.create(name='Matemática', code='MAT', teacher=self.teacher)
        second_teacher = User.objects.create_user(
            username='teach_dept_2',
            email='teach_dept_2@test.com',
            password='testpass123',
            role='t',
            is_active=True,
            first_name='Grace',
            last_name='Hopper',
        )
        second_department = Department.objects.create(name='Física', code='FIS', teacher=second_teacher)
        subject = Subject.objects.create(
            name='Álgebra lineal',
            code='ALG3',
            career=self.career,
            department=first_department,
            is_active=True,
        )

        change_response = self.client.patch(
            f'/api/academic/subjects/{subject.id}/',
            {'department': second_department.id},
            format='json',
        )
        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(change_response.json()['department'], second_department.id)

        clear_response = self.client.patch(
            f'/api/academic/subjects/{subject.id}/',
            {'department': None},
            format='json',
        )
        self.assertEqual(clear_response.status_code, 200)
        self.assertIsNone(clear_response.json()['department'])

        subject.refresh_from_db()
        self.assertIsNone(subject.department)
