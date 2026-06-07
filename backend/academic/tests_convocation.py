from django.core.exceptions import ValidationError
from django.test import TestCase

from users.models import User
from academic.models import Career, Subject
from academic.serializers import SubjectSerializer


class SubjectConvocationLimitTests(TestCase):

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teach_convocations',
            email='teach_convocations@test.com',
            password='testpass123',
            role='t',
            is_active=True,
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING-CONV')

    def test_subject_defaults_to_six_convocations(self):
        subject = Subject.objects.create(
            name='Álgebra',
            code='ALG-CONV-1',
            career=self.career,
        )

        self.assertEqual(subject.max_convocations, 6)

    def test_subject_accepts_configured_convocation_limit(self):
        subject = Subject.objects.create(
            name='Física',
            code='FIS-CONV-1',
            career=self.career,
            max_convocations=4,
        )

        self.assertEqual(subject.max_convocations, 4)

    def test_subject_rejects_non_positive_convocation_limit(self):
        subject = Subject(
            name='Química',
            code='QUI-CONV-1',
            career=self.career,
            max_convocations=0,
        )

        with self.assertRaises(ValidationError):
            subject.full_clean()

    def test_subject_serializer_exposes_max_convocations(self):
        subject = Subject.objects.create(
            name='Cálculo',
            code='CAL-CONV-1',
            career=self.career,
            max_convocations=5,
        )

        data = SubjectSerializer(subject).data

        self.assertIn('max_convocations', data)
        self.assertEqual(data['max_convocations'], 5)
