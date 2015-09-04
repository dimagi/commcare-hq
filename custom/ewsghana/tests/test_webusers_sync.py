import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.users.models import WebUser, UserRole, CommCareUser
from custom.ewsghana.api import EWSUser, EWSApi, Product, Location

from custom.ewsghana.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-webusers-test'


class WebUsersSyncTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        cls.api_object = EWSApi(TEST_DOMAIN, cls.endpoint)
        cls.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        cls.api_object.prepare_commtrack_config()
        cls.api_object.create_or_edit_roles()
        with open(os.path.join(cls.datapath, 'sample_products.json')) as f:
            for p in json.loads(f.read()):
                cls.api_object.product_sync(Product(p))

        with open(os.path.join(cls.datapath, 'sample_locations.json')) as f:
            for loc in json.loads(f.read()):
                cls.api_object.location_sync(Location(loc))

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()

    def tearDown(self):
        for user in WebUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_webuser(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = EWSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(WebUser.by_domain(TEST_DOMAIN)))
        ewsghana_webuser = self.api_object.web_user_sync(webuser)
        self.assertEqual(webuser.email, ewsghana_webuser.username)
        self.assertEqual(webuser.password, ewsghana_webuser.password)
        self.assertEqual(webuser.first_name, ewsghana_webuser.first_name)
        self.assertEqual(webuser.last_name, ewsghana_webuser.last_name)
        self.assertEqual(webuser.is_active, ewsghana_webuser.is_active)
        self.assertEqual(False, ewsghana_webuser.is_superuser)
        self.assertEqual(False, ewsghana_webuser.is_staff)
        self.assertIsNone(ewsghana_webuser.get_domain_membership(TEST_DOMAIN).location_id)
        domain_name = ewsghana_webuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
        self.assertEqual(UserRole.get_read_only_role_by_domain(TEST_DOMAIN)._id,
                         ewsghana_webuser.get_domain_membership(TEST_DOMAIN).role_id)
        ewsghana_webuser.delete()

    def test_create_facility_manager(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = EWSUser(json.loads(f.read())[1])

        self.assertEqual(0, len(WebUser.by_domain(TEST_DOMAIN)))
        ewsghana_webuser = self.api_object.web_user_sync(webuser)
        web_users = list(WebUser.by_domain(TEST_DOMAIN))
        self.assertEqual(1, len(web_users))
        facility_manager_role = UserRole.by_domain_and_name(TEST_DOMAIN, 'Facility manager')[0]
        dm = web_users[0].get_domain_membership(TEST_DOMAIN)
        self.assertEqual(facility_manager_role.get_id, dm.role_id)
        location = SQLLocation.objects.get(external_id=1, domain=TEST_DOMAIN)
        self.assertEqual(ewsghana_webuser.get_domain_membership(TEST_DOMAIN).location_id, location.location_id)

        sms_users = list(CommCareUser.by_domain(TEST_DOMAIN))
        self.assertEqual(len(sms_users), 1)

        sms_user = sms_users[0]

        self.assertEqual(sms_user.location_id, location.location_id)

    def test_create_web_reporter(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = EWSUser(json.loads(f.read())[2])
        ewsghana_webuser = self.api_object.web_user_sync(webuser)
        web_users = list(WebUser.by_domain(TEST_DOMAIN))
        self.assertEqual(1, len(web_users))
        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        web_reporter_role = UserRole.by_domain_and_name(TEST_DOMAIN, 'Web Reporter')[0]
        dm = web_users[0].get_domain_membership(TEST_DOMAIN)
        self.assertEqual(web_reporter_role.get_id, dm.role_id)
        location = SQLLocation.objects.get(external_id=620, domain=TEST_DOMAIN)
        self.assertEqual(location.location_id, ewsghana_webuser.get_domain_membership(TEST_DOMAIN).location_id)
