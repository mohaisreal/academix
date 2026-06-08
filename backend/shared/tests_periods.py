from django.test import TestCase

from academic.models import AcademicPeriod
from shared.periods import get_active_academic_period


class ActiveAcademicPeriodResolverTests(TestCase):
    def test_returns_latest_active_period_by_start_date(self):
        older = AcademicPeriod.objects.create(
            name='2025-A',
            code='2025A',
            start_date='2025-01-01',
            end_date='2025-06-30',
            is_active=True,
        )
        newer = AcademicPeriod.objects.create(
            name='2026-A',
            code='2026A',
            start_date='2026-01-01',
            end_date='2026-06-30',
            is_active=True,
        )

        resolved = get_active_academic_period()

        self.assertEqual(resolved, newer)
        self.assertNotEqual(resolved, older)

    def test_returns_none_when_no_active_period_exists(self):
        AcademicPeriod.objects.create(
            name='2025-A',
            code='2025A',
            start_date='2025-01-01',
            end_date='2025-06-30',
            is_active=False,
        )

        self.assertIsNone(get_active_academic_period())
