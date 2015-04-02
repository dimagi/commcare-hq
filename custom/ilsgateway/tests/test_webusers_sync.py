from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import WebUser, UserRole
from custom.ilsgateway.api import ILSUser, ILSGatewayAPI
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.logistics.commtrack import synchronization
from custom.logistics.models import MigrationCheckpoint

TEST_DOMAIN = 'ilsgateway-commtrack-webusers-test'


class WebUsersSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)

        for user in WebUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_webuser(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = ILSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(WebUser.by_domain(TEST_DOMAIN)))
        ilsgateway_webuser = self.api_object.web_user_sync(webuser)
        self.assertEqual(webuser.email, ilsgateway_webuser.username)
        self.assertEqual(webuser.password, ilsgateway_webuser.password)
        self.assertEqual(webuser.first_name, ilsgateway_webuser.first_name)
        self.assertEqual(webuser.last_name, ilsgateway_webuser.last_name)
        self.assertEqual(webuser.is_active, ilsgateway_webuser.is_active)
        self.assertEqual(False, ilsgateway_webuser.is_superuser)
        self.assertEqual(False, ilsgateway_webuser.is_staff)
        # self.assertEqual(webuser.location, ilsgateway_webuser.location)
        # self.assertEqual(webuser.supply_point, ilsgateway_webuser.supply_point)
        domain_name = ilsgateway_webuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
        self.assertEqual(UserRole.get_read_only_role_by_domain(TEST_DOMAIN)._id,
                         ilsgateway_webuser.get_domain_membership(TEST_DOMAIN).role_id)

    def test_webusers_migration(self):
        checkpoint = MigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.utcnow(),
            date=datetime.utcnow(),
            api='product',
            limit=100,
            offset=0
        )
        synchronization('webuser',
                        self.endpoint.get_webusers,
                        self.api_object.web_user_sync, checkpoint, None, 100, 0)
        self.assertEqual('webuser', checkpoint.api)
        self.assertEqual(100, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(5, len(list(WebUser.by_domain(TEST_DOMAIN))))
