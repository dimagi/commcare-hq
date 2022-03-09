from corehq.apps.integration.models import HmacCalloutSettings

from corehq.apps.linked_domain.local_accessors import get_hmac_callout_settings
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_hmac_callout_settings


class TestUpdateHmacCalloutSettings(BaseLinkedDomainTest):
    def setUp(self):
        self.hmac_setup = HmacCalloutSettings(domain=self.domain,
                                              destination_url='a1b2c3',
                                              is_enabled=True,
                                              api_key='abc123',
                                              api_secret='dimagi_rox')
        self.hmac_setup.save()

    def tearDown(self):
        self.hmac_setup.delete()

    def test_update_dialer_settings(self):
        self.assertEqual({'domain': self.linked_domain,
                          'destination_url': '',
                          'api_key': '',
                          'api_secret': '',
                          'is_enabled': False}, get_hmac_callout_settings(self.linked_domain))

        # Initial update of linked domain
        update_hmac_callout_settings(self.domain_link)

        # Linked domain should now have master domain's hmac callout settings
        model = HmacCalloutSettings.objects.get(domain=self.linked_domain)

        self.assertEqual(model.destination_url, 'a1b2c3')
        self.assertTrue(model.is_enabled)
        self.assertEqual(model.api_key, 'abc123')
        self.assertEqual(model.api_secret, 'dimagi_rox')

        # Updating master reflected in linked domain after update
        self.hmac_setup.destination_url = 'abc000'
        self.hmac_setup.save()
        update_hmac_callout_settings(self.domain_link)

        model = HmacCalloutSettings.objects.get(domain=self.linked_domain)
        self.assertEqual(model.destination_url, 'abc000')
