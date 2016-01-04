import os
from django.test import TestCase
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from corehq.apps.users.models import WebUser, CommCareUser
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.ilsgateway.utils import ils_bootstrap_domain_test_task


TEST_DOMAIN = 'ilsgateway-commtrack-migration-test'


class MigrationTaskTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        self.sms_backend = TestSMSBackend(name="MOBILE_BACKEND_TEST", is_global=True)
        self.sms_backend._id = self.sms_backend.name
        self.sms_backend.save()

        config = ILSGatewayConfig()
        config.domain = TEST_DOMAIN
        config.enabled = True
        config.password = 'dummy'
        config.username = 'dummy'
        config.url = 'http://test-api.com/'
        config.save()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()

    def tearDown(self):
        self.sms_backend.delete()

    def test_migration(self):
        ils_bootstrap_domain_test_task(TEST_DOMAIN, MockEndpoint('http://test-api.com/', 'dummy', 'dummy'))
        self.assertEqual(6, len(list(Product.by_domain(TEST_DOMAIN))))
        self.assertEqual(5, len(list(Location.by_domain(TEST_DOMAIN))))
        self.assertEqual(6, len(list(CommCareUser.by_domain(TEST_DOMAIN))))
        self.assertEqual(5, len(list(WebUser.by_domain(TEST_DOMAIN))))

    @classmethod
    def tearDownClass(cls):
        for user in WebUser.by_domain(TEST_DOMAIN):
            user.delete()
