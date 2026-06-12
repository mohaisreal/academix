import importlib
import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from backend.settings import (
    DEBUG,
    STORAGES,
    TIME_ZONE,
    _missing_production_email_settings,
    _missing_production_media_settings,
    _missing_production_stripe_settings,
    _missing_stripe_settings_for_mode,
    _stripe_credentials_prefix_mismatch,
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
            _missing_production_stripe_settings('', '', '', False, ''),
            ['STRIPE_LIVE_PAYMENTS_ENABLED', 'STRIPE_PUBLIC_KEY'],
        )

    def test_missing_live_flag_is_reported_even_when_demo_mode_is_allowed(self):
        self.assertEqual(
            _missing_production_stripe_settings('sk_test', 'pk_test', '', False, ''),
            ['STRIPE_LIVE_PAYMENTS_ENABLED'],
        )

    def test_live_stripe_requires_secret_and_webhook(self):
        self.assertEqual(
            _missing_production_stripe_settings('', 'pk_test', '', True, 'True'),
            ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        )

    def test_stripe_test_mode_requires_test_credentials(self):
        self.assertEqual(
            _missing_stripe_settings_for_mode('stripe_test', '', 'pk_test', '', False, ''),
            ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
        )

    def test_stripe_test_mode_rejects_live_prefixed_keys(self):
        self.assertEqual(
            _stripe_credentials_prefix_mismatch('stripe_test', 'sk_live_abc', 'pk_test_abc'),
            ['STRIPE_SECRET_KEY'],
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

    def test_settings_imports_with_smtp_backend_before_production_validation(self):
        env = {
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret-key',
            'ALLOWED_HOSTS': 'localhost',
            'CORS_ALLOWED_ORIGINS': 'http://localhost:4321',
            'CSRF_TRUSTED_ORIGINS': 'http://localhost:4321',
            'DATABASE_URL': 'sqlite:///tmp.db',
            'JWT_ACCESS_TOKEN_LIFETIME': '60',
            'JWT_REFRESH_TOKEN_LIFETIME': '1440',
            'ADMISSION_WAITLIST_GRACE_DAYS': '3',
            'AWS_ACCESS_KEY_ID': 'aws-key',
            'AWS_SECRET_ACCESS_KEY': 'aws-secret',
            'AWS_STORAGE_BUCKET_NAME': 'bucket',
            'AWS_S3_REGION_NAME': 'eu-west-1',
            'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'EMAIL_HOST': 'smtp.example.com',
            'EMAIL_PORT': '587',
            'EMAIL_HOST_USER': 'user',
            'EMAIL_HOST_PASSWORD': 'pass',
            'STRIPE_SECRET_KEY': 'sk_test',
            'STRIPE_PUBLIC_KEY': 'pk_test',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test',
            'STRIPE_LIVE_PAYMENTS_ENABLED': 'True',
        }

        with patch.dict(os.environ, env, clear=False):
            import backend.settings as settings_module

            reloaded = importlib.reload(settings_module)

        self.assertEqual(reloaded.EMAIL_BACKEND, 'django.core.mail.backends.smtp.EmailBackend')

    def test_invalid_production_email_backend_raises_improperly_configured(self):
        env = {
            'DEBUG': 'False',
            'SECRET_KEY': 'test-secret-key',
            'ALLOWED_HOSTS': 'localhost',
            'CORS_ALLOWED_ORIGINS': 'http://localhost:4321',
            'CSRF_TRUSTED_ORIGINS': 'http://localhost:4321',
            'DATABASE_URL': 'sqlite:///tmp.db',
            'JWT_ACCESS_TOKEN_LIFETIME': '60',
            'JWT_REFRESH_TOKEN_LIFETIME': '1440',
            'ADMISSION_WAITLIST_GRACE_DAYS': '3',
            'AWS_ACCESS_KEY_ID': 'aws-key',
            'AWS_SECRET_ACCESS_KEY': 'aws-secret',
            'AWS_STORAGE_BUCKET_NAME': 'bucket',
            'AWS_S3_REGION_NAME': 'eu-west-1',
            'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
            'EMAIL_HOST': 'smtp.example.com',
            'EMAIL_PORT': '587',
            'EMAIL_HOST_USER': 'user',
            'EMAIL_HOST_PASSWORD': 'pass',
            'STRIPE_SECRET_KEY': 'sk_test',
            'STRIPE_PUBLIC_KEY': 'pk_test',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test',
            'STRIPE_LIVE_PAYMENTS_ENABLED': 'True',
        }

        with patch.dict(os.environ, env, clear=False):
            import backend.settings as settings_module

            with self.assertRaises(ImproperlyConfigured) as context:
                importlib.reload(settings_module)

        self.assertIn('EMAIL_BACKEND', str(context.exception))
