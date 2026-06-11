from django.test import SimpleTestCase, override_settings


@override_settings(DEBUG=True, STATIC_URL='/static/')
class StaticFilesDevRoutingTests(SimpleTestCase):
    def test_static_url_is_normalized_with_leading_slash(self):
        from django.conf import settings

        self.assertEqual(settings.STATIC_URL, '/static/')

    def test_admin_static_asset_is_served_without_collectstatic(self):
        response = self.client.get('/static/admin/css/base.css')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/css', response['Content-Type'])
