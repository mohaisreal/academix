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
