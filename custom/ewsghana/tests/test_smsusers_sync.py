import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.api import EWSApi, SMSUser

from custom.ilsgateway.tests.mock_endpoint import MockEndpoint

TEST_DOMAIN = 'ewsghana-commtrack-smsusers-test'


class SMSUsersSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = EWSApi(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)
        self.api_object.prepare_commtrack_config()
        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_smsuser(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertIsNotNone(ewsghana_smsuser.get_id)
        username_part = "%s%d" % (ewsghana_smsuser.name.strip().replace(' ', '.').lower(), smsuser.id)
        username = "%s@%s.commcarehq.org" % (username_part, TEST_DOMAIN)
        self.assertEqual(username, ewsghana_smsuser.username)
        self.assertEqual(smsuser.is_active, str(ewsghana_smsuser.is_active))
        self.assertEqual(False, ewsghana_smsuser.is_superuser)
        self.assertEqual(False, ewsghana_smsuser.is_staff)
        domain_name = ewsghana_smsuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
