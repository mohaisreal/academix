from django.core.management.base import BaseCommand

from admissions.services.expiry_sweep import run_admission_expiry_sweep


class Command(BaseCommand):
    help = 'Run admissions grace expiry sweep.'

    def add_arguments(self, parser):
        parser.add_argument('--period-id', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        result = run_admission_expiry_sweep(period_id=options['period_id'], dry_run=options['dry_run'])
        self.stdout.write(str(result))
