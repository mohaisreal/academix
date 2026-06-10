from django.test import SimpleTestCase

from backend.settings import (
    DEBUG,
    STORAGES,
    TIME_ZONE,
    _missing_production_email_settings,
    _missing_production_media_settings,
    _missing_production_stripe_settings,
)


class ProductionStorageConfigTests(SimpleTestCase):
    def test_missing_production_aws_settings_are_reported(self):
        self.assertEqual(
            _missing_production_media_settings('', '', '', ''),
            ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_STORAGE_BUCKET_NAME', 'AWS_S3_REGION_NAME'],
        )

    def test_storage_backend_matches_runtime_mode(self):
        expected_backend = (
            'django.core.files.storage.FileSystemStorage'
            if DEBUG
            else 'storages.backends.s3boto3.S3Boto3Storage'
        )

        self.assertEqual(STORAGES['default']['BACKEND'], expected_backend)


class ProductionStripeConfigTests(SimpleTestCase):
    def test_missing_production_stripe_settings_are_reported(self):
        self.assertEqual(
            _missing_production_stripe_settings('', '', '', False),
            ['STRIPE_SECRET_KEY', 'STRIPE_PUBLIC_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_LIVE_PAYMENTS_ENABLED'],
        )


class TimeZoneConfigTests(SimpleTestCase):
    def test_time_zone_defaults_to_institution_local_zone(self):
        self.assertEqual(TIME_ZONE, 'Europe/Madrid')


class ProductionEmailConfigTests(SimpleTestCase):
    def test_missing_production_email_settings_are_reported(self):
        self.assertEqual(
            _missing_production_email_settings('', '', '', '', ''),
            ['EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'],
        )

    def test_non_smtp_backend_is_reported(self):
        self.assertEqual(
            _missing_production_email_settings('django.core.mail.backends.console.EmailBackend', 'smtp.example.com', 587, 'user', 'pass'),
            ['EMAIL_BACKEND'],
        )
