from pathlib import Path

from django.test import SimpleTestCase, RequestFactory, override_settings
from django.urls import resolve


@override_settings(DEBUG=True, STATIC_URL='/static/')
class StaticFilesDevRoutingTests(SimpleTestCase):
    def test_static_url_is_normalized_with_leading_slash(self):
        from django.conf import settings

        self.assertEqual(settings.STATIC_URL, '/static/')

    def test_admin_static_asset_is_served_without_collectstatic(self):
        match = resolve('/static/admin/css/base.css')
        response = match.func(RequestFactory().get('/static/admin/css/base.css'), **match.kwargs)

        self.assertEqual(match.func.__name__, 'dev_static_serve')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/css', response['Content-Type'])


class ProductionDeploymentContractTests(SimpleTestCase):
    def test_prod_compose_escapes_runtime_env_refs(self):
        compose_path = Path(__file__).resolve().parents[2] / 'docker-compose.prod.yml'
        content = compose_path.read_text(encoding='utf-8')

        self.assertIn('test: ["CMD-SHELL", "pg_isready -U \\\"$${POSTGRES_USER}\\\" -d \\\"$${POSTGRES_DB}\\\""]', content)
        self.assertIn('PUBLIC_API_URL: /api', content)
        self.assertIn('BACKEND_API_URL: http://backend:8000/api', content)
        self.assertNotIn('test: ["CMD", "pg_isready", "-U", "${POSTGRES_USER}"]', content)

    def test_prod_env_uses_canonical_postgres_name(self):
        env_path = Path(__file__).resolve().parents[2] / '.env.prod.example'
        content = env_path.read_text(encoding='utf-8')

        self.assertIn('DATABASE_URL=postgres://academix:replace-with-strong-password@db:5432/academix_db', content)
        self.assertIn('POSTGRES_DB=academix_db', content)
        self.assertIn('POSTGRES_USER=academix', content)

    def test_backend_prod_defaults_use_academix_domain(self):
        settings_path = Path(__file__).resolve().parent / 'settings.py'
        content = settings_path.read_text(encoding='utf-8')

        self.assertIn("FRONTEND_URL = env('FRONTEND_URL', default='https://academix.cv')", content)
        self.assertIn("CORS_ALLOWED_ORIGINS=(list, ['https://academix.cv'])", content)
        self.assertIn("CSRF_TRUSTED_ORIGINS=(list, ['https://academix.cv'])", content)
        self.assertNotIn("default='http://localhost:4321'", content)

    def test_backend_entrypoint_checks_manage_py_from_app(self):
        entrypoint_path = Path(__file__).resolve().parents[1] / 'entrypoint.sh'
        content = entrypoint_path.read_text(encoding='utf-8')

        self.assertIn('cd /app', content)
        self.assertIn('if [ ! -f manage.py ]; then', content)
        self.assertIn('python manage.py migrate --noinput', content)

    def test_prod_compose_bootstraps_static_volume_before_backend(self):
        compose_path = Path(__file__).resolve().parents[2] / 'docker-compose.prod.yml'
        content = compose_path.read_text(encoding='utf-8')

        self.assertIn('static-volume-init:', content)
        self.assertIn('- static_data:/app/staticfiles', content)
        self.assertIn('condition: service_completed_successfully', content)

    def test_prod_backend_contract_keeps_non_root_collectstatic_flow(self):
        compose_path = Path(__file__).resolve().parents[2] / 'docker-compose.prod.yml'
        dockerfile_path = Path(__file__).resolve().parents[1] / 'Dockerfile'

        compose_content = compose_path.read_text(encoding='utf-8')
        dockerfile_content = dockerfile_path.read_text(encoding='utf-8')
        backend_block = compose_content.split('  frontend:')[0]

        self.assertIn('collectstatic --noinput', Path(__file__).resolve().parents[1].joinpath('entrypoint.sh').read_text(encoding='utf-8'))
        self.assertIn('USER appuser', dockerfile_content)
        self.assertIn('useradd -m -u 1000 appuser', dockerfile_content)
        self.assertNotIn('user: root', backend_block)
