from django.test import TestCase
from django.urls import reverse

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.motech.auth import BasicAuthManager
from corehq.motech.const import ALGO_AES, BASIC_AUTH
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterXMLPayloadGenerator,
)
from corehq.motech.repeaters.views import AddFormRepeaterView

DOMAIN = 'meaning-of-life'
URL = 'https://restaurant.fr/api/'
USERNAME = 'terry'
PASSWORD = 'wafer-thin_mint'
ADMIN = 'admin@example.com'


class ConnectionSettingsAuthManagerTests(TestCase):

    def test_connection_settings_auth_manager(self):
        connx = ConnectionSettings(
            domain=DOMAIN,
            name='Mr. Creosote',
            url=URL,
            auth_type=BASIC_AUTH,
            username=USERNAME,
            password='',
            notify_addresses_str=ADMIN,
        )
        connx.plaintext_password = PASSWORD
        connx.save()
        try:
            auth_manager = connx.get_auth_manager()
            self.assertIsInstance(auth_manager, BasicAuthManager)
            self.assertEqual(auth_manager.username, USERNAME)
            self.assertEqual(auth_manager.password, PASSWORD)
            self.assertNotEqual(auth_manager.password, connx.password)
            self.assertTrue(connx.password.startswith(f'${ALGO_AES}$'))
        finally:
            connx.delete()


class RepeaterAuthManagerTests(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(name=DOMAIN, is_active=True)
        cls.domain.save()
        cls.user = WebUser.create(DOMAIN, 'admin', 'secret', None, None, is_admin=True)
        cls.user.eula.signed = True
        cls.user.save()
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.user.delete(deleted_by=None)
        cls.domain.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def test_repeater_auth_manager(self):
        # Mimics the way Repeaters are made; similarly, it turns out, to
        # laws and sausages.
        self.client.login(
            username='admin',
            password='secret',
        )
        url = reverse(AddFormRepeaterView.urlname, kwargs={
            'domain': self.domain.name,
        })
        repeater_data = {
            'domain': DOMAIN,
            'url': URL,
            'auth_type': BASIC_AUTH,
            'username': USERNAME,
            'password': PASSWORD,
            'notify_addresses_str': ADMIN,
            'format': FormRepeaterXMLPayloadGenerator.format_name,
        }
        self.client.post(url, repeater_data, follow=True)

        repeater = FormRepeater.by_domain(DOMAIN)[0]
        try:
            auth_manager = repeater.get_auth_manager()
            self.assertIsInstance(auth_manager, BasicAuthManager)
            self.assertEqual(auth_manager.username, USERNAME)
            self.assertEqual(auth_manager.password, PASSWORD)
            self.assertNotEqual(auth_manager.password, repeater.password)
            self.assertTrue(repeater.password.startswith(f'${ALGO_AES}$'))
        finally:
            for repeater in FormRepeater.by_domain(DOMAIN):
                repeater.delete()
