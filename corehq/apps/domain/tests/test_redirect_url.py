from contextlib import contextmanager
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test-redirect-url'


class TestRedirectUrlCommand(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_data_migration_not_enabled(self):
        with self.assertRaisesRegex(
            CommandError,
            r'^Domain test\-redirect\-url is not migrated\.$'
        ):
            self._call_redirect_url('--set', 'https://example.com/')

    @flag_enabled('DATA_MIGRATION')
    def test_no_https(self):
        with self.assertRaisesRegex(
            CommandError,
            r'^http://example.com/ is not a secure URL\.$'
        ):
            self._call_redirect_url('--set', 'http://example.com/')

    @flag_enabled('DATA_MIGRATION')
    def test_bad_url(self):
        with self.assertRaisesRegex(
            CommandError,
            r'^https://example/ is not a valid URL\.$'
        ):
            self._call_redirect_url('--set', 'https://example/')

    @flag_enabled('DATA_MIGRATION')
    def test_set_url(self):
        stdout = self._call_redirect_url('--set', 'https://example.com/')
        self.assertEqual(
            stdout,
            'App updates are redirected to https://example.com/\n'
        )

    def test_unset_url_data_migration_not_enabled(self):
        with _set_redirect_url():
            stdout = self._call_redirect_url('--unset')
            self.assertEqual(stdout, 'Redirect URL not set\n')

    @flag_enabled('DATA_MIGRATION')
    def test_unset_url_migration_enabled(self):
        with _set_redirect_url():
            stdout = self._call_redirect_url('--unset')
            self.assertEqual(stdout, 'Redirect URL not set\n')

    def test_return_set_url_data_migration_not_enabled(self):
        with _set_redirect_url():
            stdout = self._call_redirect_url()
            self.assertEqual(
                stdout,
                'App updates are redirected to https://example.com/\n'
            )

    @flag_enabled('DATA_MIGRATION')
    def test_return_set_url_migration_enabled(self):
        with _set_redirect_url():
            stdout = self._call_redirect_url()
            self.assertEqual(
                stdout,
                'App updates are redirected to https://example.com/\n'
            )

    def test_return_unset_url_data_migration_not_enabled(self):
        stdout = self._call_redirect_url()
        self.assertEqual(stdout, 'Redirect URL not set\n')

    @flag_enabled('DATA_MIGRATION')
    def test_return_unset_url_migration_enabled(self):
        stdout = self._call_redirect_url()
        self.assertEqual(stdout, 'Redirect URL not set\n')

    @staticmethod
    def _call_redirect_url(*args, **kwargs):
        stdout = StringIO()
        call_command(
            'redirect_url', DOMAIN, *args,
            stdout=stdout, **kwargs,
        )
        return stdout.getvalue()


class TestCheckDomainMigration(TestCase):
    """
    Tests the ``download_odk_media_profile`` view, which is wrapped with
    the ``corehq.apps.app_manager.decorators.check_redirect`` decorator.

    All relevant views are protected by that decorator. These tests
    verify that the decorator returns a 302 redirect response when the
    domain's ``redirect_url`` is set, and a normal response when it is
    not set.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.app = Application.new_app(DOMAIN, "TestApp")
        cls.app.save()
        cls.client = Client()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_redirect_response(self):
        with _set_redirect_url():
            response = self._download_odk_media_profile()
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response.url,
                f'https://example.com/a/{DOMAIN}/apps/download/{self.app._id}'
                '/media_profile.ccpr?latest=true'
                f'&username=user%40{DOMAIN}.commcarehq.org'
            )

    def test_normal_response(self):
        response = self._download_odk_media_profile()
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode('utf-8'),
            r"^<\?xml version='1.0' encoding='UTF-8'\?>"
        )

    @flag_enabled('DATA_MIGRATION')
    def test_data_migration_doesnt_block_updates(self):
        response = self._download_odk_media_profile()
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode('utf-8'),
            r"^<\?xml version='1.0' encoding='UTF-8'\?>"
        )

    @flag_enabled('DISABLE_MOBILE_ENDPOINTS')
    def test_disable_endpoints_blocks_updates(self):
        response = self._download_odk_media_profile()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.content.decode('utf-8'),
            'Service Temporarily Unavailable'
        )

    @flag_enabled('DISABLE_MOBILE_ENDPOINTS')
    def test_redirect_overrides_disable(self):
        with _set_redirect_url():
            response = self._download_odk_media_profile()
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response.url,
                f'https://example.com/a/{DOMAIN}/apps/download/{self.app._id}'
                '/media_profile.ccpr?latest=true'
                f'&username=user%40{DOMAIN}.commcarehq.org'
            )

    def _download_odk_media_profile(self):
        return self.client.get(reverse(
            'download_odk_media_profile',
            args=[DOMAIN, self.app._id],
        ), {'latest': 'true', 'username': f'user@{DOMAIN}.commcarehq.org'})


@contextmanager
def _set_redirect_url():
    domain_obj = Domain.get_by_name(DOMAIN)
    domain_obj.redirect_url = 'https://example.com/'
    domain_obj.save()
    try:
        yield
    finally:
        domain_obj = Domain.get_by_name(DOMAIN)
        domain_obj.redirect_url = ''
        domain_obj.save()
