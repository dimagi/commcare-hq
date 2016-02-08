import os
from django.test import TestCase
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import Location
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.users.models import WebUser, CommCareUser
from custom.ilsgateway.api import ILSGatewayAPI
from custom.ilsgateway.models import ILSGatewayConfig, ILSMigrationStats, ILSMigrationProblem
from custom.ilsgateway.tasks import balance_migration_task
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.logistics.commtrack import bootstrap_domain

TEST_DOMAIN = 'ilsgateway-commtrack-migration-test'


class MigrationTaskTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.datapath = os.path.join(os.path.dirname(__file__), 'data')
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        initial_bootstrap(TEST_DOMAIN)

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
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()

        for location in Location.by_domain(TEST_DOMAIN):
            location.delete()

        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

        for web_user in WebUser.by_domain(TEST_DOMAIN):
            web_user.delete()

        ILSMigrationStats.objects.all().delete()
        ILSMigrationProblem.objects.all().delete()

    def test_migration(self):
        bootstrap_domain(ILSGatewayAPI(TEST_DOMAIN, MockEndpoint('http://test-api.com/', 'dummy', 'dummy')))
        self.assertEqual(6, len(list(Product.by_domain(TEST_DOMAIN))))
        self.assertEqual(6, len(list(Location.by_domain(TEST_DOMAIN))))
        self.assertEqual(6, len(list(CommCareUser.by_domain(TEST_DOMAIN))))
        self.assertEqual(5, len(list(WebUser.by_domain(TEST_DOMAIN))))
        self.assertEqual(ILSMigrationStats.objects.filter(domain=TEST_DOMAIN).count(), 1)

    def test_balance(self):
        endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        bootstrap_domain(ILSGatewayAPI(TEST_DOMAIN, endpoint))
        self.assertEqual(ILSMigrationStats.objects.filter(domain=TEST_DOMAIN).count(), 1)
        self.assertEqual(ILSMigrationProblem.objects.count(), 0)

        web_user = WebUser.get_by_username('ilsgateway@gmail.com')
        web_user.get_domain_membership(TEST_DOMAIN).location_id = None
        web_user.save()

        sms_user = CommCareUser.by_domain(TEST_DOMAIN)[0]
        sms_user.phone_numbers = []
        sms_user.save()

        balance_migration_task(TEST_DOMAIN, endpoint)
        self.assertEqual(ILSMigrationProblem.objects.count(), 2)

        bootstrap_domain(ILSGatewayAPI(TEST_DOMAIN, endpoint))
        self.assertEqual(ILSMigrationProblem.objects.count(), 0)

    @classmethod
    def tearDownClass(cls):
        cls.sms_backend_mapping.delete()
        cls.sms_backend.delete()
        for user in WebUser.by_domain(TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(TEST_DOMAIN):
            vn.delete()
