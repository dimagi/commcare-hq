from contextlib import contextmanager
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.const import OPENROSA_VERSION_2
from corehq.middleware import OPENROSA_VERSION_HEADER
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
            'Form submissions and syncs are redirected to '
            'https://example.com/\n'
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
                'Form submissions and syncs are redirected to '
                'https://example.com/\n'
            )

    @flag_enabled('DATA_MIGRATION')
    def test_return_set_url_migration_enabled(self):
        with _set_redirect_url():
            stdout = self._call_redirect_url()
            self.assertEqual(
                stdout,
                'Form submissions and syncs are redirected to '
                'https://example.com/\n'
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
    Tests the ``receiver_post`` view, which is wrapped with the
    ``corehq.apps.domain.decorators.check_domain_migration`` decorator.

    All relevant views are protected by that decorator during and after
    data migration. These tests verify that the decorator returns a 308
    redirect response when the domain's ``redirect_url`` is set, and a
    503 service unavailable response when it is not set.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.user = WebUser.create(
            None, 'admin', 'Passw0rd!',
            None, None,
        )
        cls.user.add_domain_membership(DOMAIN, is_admin=True)
        cls.user.save()
        cls.client = Client()
        cls.client.login(username='admin', password='Passw0rd!')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(DOMAIN, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @flag_enabled('DATA_MIGRATION')
    def test_redirect_response(self):
        with _set_redirect_url():
            response = self._submit_form()
            self.assertEqual(response.status_code, 308)
            self.assertEqual(response.url, 'https://example.com/')

    @flag_enabled('DATA_MIGRATION')
    def test_service_unavailable_response(self):
        response = self._submit_form()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.content.decode('utf-8'),
            'Service Temporarily Unavailable',
        )

    def _submit_form(self):
        form = """<?xml version='1.0' ?>
        <form>Not a real form</form>
        """
        with StringIO(form) as f:
            response = self.client.post(
                reverse("receiver_post", args=[DOMAIN]),
                {"xml_submission_file": f},
                **{OPENROSA_VERSION_HEADER: OPENROSA_VERSION_2}
            )
        return response


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
