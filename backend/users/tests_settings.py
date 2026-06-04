from django.test import SimpleTestCase

from backend.settings import (
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


class ProductionStripeConfigTests(SimpleTestCase):
    def test_missing_production_stripe_settings_are_reported(self):
        self.assertEqual(
            _missing_production_stripe_settings('', '', '', False),
            ['STRIPE_SECRET_KEY', 'STRIPE_PUBLIC_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_LIVE_PAYMENTS_ENABLED'],
        )


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
