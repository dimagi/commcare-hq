import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import WebUser, UserRole, CommCareUser
from custom.ewsghana.api import EWSUser, EWSApi

from custom.ilsgateway.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-webusers-test'


class WebUsersSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = EWSApi(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        self.api_object.prepare_commtrack_config()
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
        domain_name = ewsghana_webuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
        self.assertEqual(UserRole.get_read_only_role_by_domain(TEST_DOMAIN)._id,
                         ewsghana_webuser.get_domain_membership(TEST_DOMAIN).role_id)

    def test_create_facility_manager(self):
        """
            Facility manager in EWS is created as web user but in HQ
            is converted to CommTrackUser
        """
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = EWSUser(json.loads(f.read())[1])

        self.assertEqual(0, len(WebUser.by_domain(TEST_DOMAIN)))
        self.api_object.web_user_sync(webuser)
        self.assertEqual(0, len(list(WebUser.by_domain(TEST_DOMAIN))))
        users = CommCareUser.by_domain(TEST_DOMAIN)
        self.assertEqual(1, len(list(users)))
