from contextlib import contextmanager

from django.contrib.messages import get_messages
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from bs4 import BeautifulSoup
from unittest.mock import patch

from corehq import privileges
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.settings import EditDomainAlertView, ManageDomainAlertsView, MAX_ACTIVE_ALERTS
from corehq.apps.hqwebapp.models import Alert
from corehq.apps.users.models import WebUser
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import AppStructureRepeater
from corehq.util.test_utils import privilege_enabled


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
        self.user.delete(self.domain.name, deleted_by=None)
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
                {'connection_settings_id': connx.id, 'request_method': "POST"},
                follow=True
            )
            self.assertEqual(response.status_code, 200)

            app_structure_repeaters = AppStructureRepeater.objects.by_domain(self.domain.name)
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
            soup = BeautifulSoup(response.content, features="lxml")
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


class TestBaseDomainAlertView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_name = 'gotham'
        cls.domain = Domain(name=cls.domain_name, is_active=True)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)

        cls.other_domain_name = 'krypton'

        cls.username = 'batman@gotham.com'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain_name, cls.username, cls.password,
                                  created_by=None, created_via=None, is_admin=True)
        cls.addClassCleanup(cls.user.delete, deleted_by_domain=cls.domain_name, deleted_by=None)

        cls.domain_alert = cls._create_alert_for_domain(cls.domain_name, 'Test Alert 1!', cls.username)
        cls.other_domain_alert = cls._create_alert_for_domain(cls.other_domain_name, 'Test Alert 2!', cls.username)

    @staticmethod
    def _create_alert_for_domain(domain, alert_text, username):
        return Alert.objects.create(
            text=alert_text,
            domains=[domain],
            created_by_domain=domain,
            created_by_user=username
        )

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username=self.username, password=self.password)

    def ensure_valid_access_only(self, use_post=False):
        if use_post:
            response = self.client.post(self.url)
        else:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)


class TestManageDomainAlertsView(TestBaseDomainAlertView):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.url = reverse(ManageDomainAlertsView.urlname, kwargs={
            'domain': cls.domain_name,
        })

    def test_valid_access_only(self):
        self.ensure_valid_access_only()

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_only_domain_alerts_listed(self):
        alert = self.domain_alert

        response = self.client.get(self.url)
        self.assertListEqual(
            response.context['alerts'],
            [
                {
                    'start_time': None, 'end_time': None,
                    'active': False, 'html': 'Test Alert 1!', 'id': alert.id, 'created_by_user': self.username
                }
            ]
        )
        self.assertEqual(response.status_code, 200)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_creating_new_alert(self):
        self.assertEqual(Alert.objects.count(), 2)

        response = self.client.post(
            self.url,
            data={
                'text': 'New Alert!',
            },
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert saved!')
        self.assertEqual(response.status_code, 302)

        self.assertEqual(Alert.objects.count(), 3)

        new_alert = Alert.objects.order_by('pk').last()
        self.assertEqual(new_alert.html, "New Alert!")
        self.assertEqual(new_alert.created_by_domain, self.domain.name)
        self.assertListEqual(new_alert.domains, [self.domain.name])

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_creating_new_alert_with_errors(self):
        self.assertEqual(Alert.objects.count(), 2)

        response = self.client.post(
            self.url,
            data={
                'text': '',
            },
        )

        self.assertEqual(Alert.objects.count(), 2)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'There was an error saving your alert. Please try again!')
        self.assertEqual(response.status_code, 200)


class TestUpdateDomainAlertStatusView(TestBaseDomainAlertView):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.url = reverse('update_domain_alert_status', kwargs={
            'domain': cls.domain_name,
        })

    def test_valid_access_only(self):
        self.ensure_valid_access_only(use_post=True)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_post_access_only(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_apply_command_with_missing_alert_id(self):
        with self.assertRaisesMessage(AssertionError, 'Missing alert ID'):
            self.client.post(
                self.url,
                data={
                    'command': 'activate',
                },
            )

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_apply_command_with_missing_alert(self):
        response = self.client.post(
            self.url,
            data={
                'command': 'activate',
                'alert_id': 0,
            },
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert not found!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_apply_command_with_invalid_command(self):
        response = self.client.post(
            self.url,
            data={
                'command': 'elevate',
                'alert_id': self.domain_alert.id,
            },
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Unexpected update received. Alert not updated!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_apply_command_with_valid_command(self):
        alert = self._create_alert_for_domain(self.domain, "New Alert!", self.username)

        self.assertFalse(alert.active)

        response = self.client.post(
            self.url,
            data={
                'command': 'activate',
                'alert_id': alert.id,
            },
        )

        alert.refresh_from_db()
        self.assertTrue(alert.active)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert updated!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_apply_command_with_other_doamin_alert(self):
        response = self.client.post(
            self.url,
            data={
                'command': 'activate',
                'alert_id': self.other_domain_alert.id,
            },
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert not found!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_limiting_active_alerts(self):
        new_alerts = [
            self._create_alert_for_domain(self.domain_name, 'New Alert 1!', self.username),
            self._create_alert_for_domain(self.domain_name, 'New Alert 2!', self.username),
            self._create_alert_for_domain(self.domain_name, 'New Alert 3!', self.username),
        ]
        for alert in new_alerts:
            alert.active = True
            alert.save()

        self.assertEqual(
            Alert.objects.filter(created_by_domain=self.domain, active=True).count(),
            MAX_ACTIVE_ALERTS
        )

        response = self.client.post(
            self.url,
            data={
                'command': 'activate',
                'alert_id': self.domain_alert.id,
            },
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert not activated. Only 3 active alerts allowed.')


class TestDeleteDomainAlertView(TestBaseDomainAlertView):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.url = reverse('delete_domain_alert', kwargs={
            'domain': cls.domain_name,
        })

    def test_valid_access_only(self):
        self.ensure_valid_access_only(use_post=True)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_post_access_only(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_with_missing_alert_id(self):
        with self.assertRaisesMessage(AssertionError, 'Missing alert ID'):
            self.client.post(
                self.url,
                data={},
            )

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_with_missing_alert(self):
        response = self.client.post(
            self.url,
            data={
                'alert_id': 0,
            },
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert not found!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_delete(self):
        response = self.client.post(
            self.url,
            data={
                'alert_id': self.domain_alert.id,
            },
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert was removed!')
        self.assertEqual(response.status_code, 302)


class TestEditDomainAlertView(TestBaseDomainAlertView):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.url = reverse(EditDomainAlertView.urlname, kwargs={
            'domain': cls.domain_name, 'alert_id': cls.domain_alert.id
        })

    def test_valid_access_only(self):
        self.ensure_valid_access_only()

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_only_domain_alerts_accessible(self):
        url = reverse(EditDomainAlertView.urlname, kwargs={
            'domain': self.domain_name, 'alert_id': self.other_domain_alert.id
        })

        with self.assertRaisesMessage(AssertionError, 'Alert not found'):
            self.client.get(url)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_only_domain_alerts_accessible_for_update(self):
        url = reverse(EditDomainAlertView.urlname, kwargs={
            'domain': self.domain_name, 'alert_id': self.other_domain_alert.id
        })
        response = self.client.post(url, data={'text': 'Bad text'})

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert not found!')
        self.assertEqual(response.status_code, 302)

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_updating_alert(self):
        text = self.domain_alert.text + ". Updated!"
        response = self.client.post(
            self.url,
            data={
                'text': text,
            },
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'Alert saved!')
        self.assertEqual(response.status_code, 302)
        self.domain_alert.refresh_from_db()
        self.assertEqual(self.domain_alert.text, 'Test Alert 1!. Updated!')

    @privilege_enabled(privileges.CUSTOM_DOMAIN_ALERTS)
    def test_updating_alert_with_errors(self):
        response = self.client.post(
            self.url,
            data={
                'text': '',
            },
        )

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages[0].message, 'There was an error saving your alert. Please try again!')
        self.assertEqual(response.status_code, 200)


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
