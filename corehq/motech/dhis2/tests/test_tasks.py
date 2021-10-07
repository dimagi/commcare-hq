from django.test import TestCase

from corehq import toggles
from corehq.motech.dhis2.tasks import send_datasets_for_all_domains


class TestSendDatasetsForAllDomains(TestCase):

    domain_name = 'does-not-exist'

    def setUp(self):
        toggles.DHIS2_INTEGRATION.set(
            self.domain_name,
            enabled=True,
            namespace=toggles.NAMESPACE_DOMAIN
        )

    def tearDown(self):
        toggles.DHIS2_INTEGRATION.set(
            self.domain_name,
            enabled=False,
            namespace=toggles.NAMESPACE_DOMAIN
        )

    def test_check_domain_exists(self):
        """
        send_datasets_for_all_domains() should not raise an AttributeError
        if a domain does not exist
        """
        send_datasets_for_all_domains()
