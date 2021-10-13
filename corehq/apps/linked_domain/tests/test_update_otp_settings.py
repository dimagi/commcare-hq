from corehq.apps.integration.models import GaenOtpServerSettings

from corehq.apps.linked_domain.local_accessors import get_otp_settings
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_otp_settings


class TestUpdateOTPSettings(BaseLinkedDomainTest):
    def setUp(self):
        self.otp_setup = GaenOtpServerSettings(domain=self.domain,
                                               is_enabled=True,
                                               server_url='a1b2c3',
                                               auth_token='auth_1234')
        self.otp_setup.save()

    def tearDown(self):
        self.otp_setup.delete()

    def test_update_otp_settings(self):
        self.assertEqual({'domain': self.linked_domain,
                          'server_url': '',
                          'auth_token': '',
                          'is_enabled': False}, get_otp_settings(self.linked_domain))

        # Initial update of linked domain
        update_otp_settings(self.domain_link)

        # Linked domain should now have master domain's otp settings
        model = GaenOtpServerSettings.objects.get(domain=self.linked_domain)

        self.assertTrue(model.is_enabled)
        self.assertEqual(model.server_url, 'a1b2c3')
        self.assertEqual(model.auth_token, 'auth_1234')

        # Updating master reflected in linked domain after update
        self.otp_setup.server_url = 'a0b0c0'
        self.otp_setup.save()
        update_otp_settings(self.domain_link)

        model = GaenOtpServerSettings.objects.get(domain=self.linked_domain)
        self.assertEqual(model.server_url, 'a0b0c0')
