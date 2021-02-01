from contextlib import contextmanager

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from bs4 import BeautifulSoup
from mock import patch

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import AppStructureRepeater


class TestDomainViews(TestCase, DomainSubscriptionMixin):

    def setUp(self):
        super().setUp()
        self.client = Client()

        self.domain = Domain(name='fandango', is_active=True)
        self.domain.save()

        # DATA_FORWARDING is on PRO and above,
        # which is needed by test_add_repeater
        self.setup_subscription(self.domain.name, SoftwarePlanEdition.PRO)

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password, None, None, is_admin=True)
        self.user.eula.signed = True
        self.user.save()

        self.app = Application.new_app(domain='fandango', name="cheeto")
        self.app.save()

    def tearDown(self):
        self.teardown_subscriptions()
        self.user.delete(deleted_by=None)
        self.domain.delete()
        clear_plan_version_cache()
        super().tearDown()

    def test_allow_domain_requests(self):
        self.client.login(username=self.username, password=self.password)

        with domain_fixture("public", allow_domain_requests=True):
            response = self.client.get(reverse("domain_homepage", args=["public"]), follow=True)
            self.assertEqual(response.status_code, 200)

    def test_disallow_domain_requests(self):
        self.client.login(username=self.username, password=self.password)

        with domain_fixture("private"):
            response = self.client.get(reverse("domain_homepage", args=["private"]), follow=True)
            self.assertEqual(response.status_code, 404)

    def test_add_repeater(self):
        self.client.login(username=self.username, password=self.password)

        with connection_fixture(self.domain.name) as connx:
            post_url = reverse('add_repeater', kwargs={
                'domain': self.domain.name,
                'repeater_type': 'AppStructureRepeater'
            })
            response = self.client.post(
                post_url,
                {'connection_settings_id': connx.id},
                follow=True
            )
            self.assertEqual(response.status_code, 200)

            app_structure_repeaters = AppStructureRepeater.by_domain(self.domain.name)
            self.assertEqual(len(app_structure_repeaters), 1)

            for app_structure_repeater in app_structure_repeaters:
                app_structure_repeater.delete()

        self.client.logout()


class BaseAutocompleteTest(TestCase):

    def verify(self, autocomplete_enabled, view_path, *fields):
        flag = not autocomplete_enabled
        setting_path = 'django.conf.settings.DISABLE_AUTOCOMPLETE_ON_SENSITIVE_FORMS'
        # HACK use patch to work around bug in override_settings
        # https://github.com/django-compressor/django-appconf/issues/30
        with patch(setting_path, flag):
            response = self.client.get(view_path)
            soup = BeautifulSoup(response.content)
            for field in fields:
                tag = soup.find("input", attrs={"name": field})
                self.assertTrue(tag, "field not found: " + field)
                print(tag)
                is_enabled = tag.get("autocomplete") != "off"
                self.assertEqual(is_enabled, autocomplete_enabled)


class TestPasswordResetFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        self.verify(True, "/accounts/password_reset_email/", "email")

    def test_autocomplete_disabled(self):
        self.verify(False, "/accounts/password_reset_email/", "email")


@contextmanager
def domain_fixture(domain_name, allow_domain_requests=False):
    domain = Domain(name=domain_name, is_active=True)
    if allow_domain_requests:
        domain.allow_domain_requests = True
    domain.save()
    try:
        yield
    finally:
        domain.delete()


@contextmanager
def connection_fixture(domain_name):
    connx = ConnectionSettings(
        domain=domain_name,
        name='example.com',
        url='https://example.com/forwarding',
    )
    connx.save()
    try:
        yield connx
    finally:
        connx.delete()
