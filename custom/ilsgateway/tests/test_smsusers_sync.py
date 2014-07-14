import json
import os
from django.test import TestCase
from corehq import Domain
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.api import SMSUser
from custom.ilsgateway.commtrack import sync_ilsgateway_smsusers

TEST_DOMAIN = 'ilsgateway-commtrack-smsusers-test'


class WebUsersSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)

        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_webuser(self):
        with open(os.path.join(self.datapath, 'sample_smsuser.json')) as f:
            smsuser = SMSUser.from_json(json.loads(f.read()))

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = sync_ilsgateway_smsusers(TEST_DOMAIN, smsuser)
        first_name, last_name = ilsgateway_smsuser.name.split(' ', 1)
        username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), smsuser.id)
        username = "%s@%s.commcarehq.org" % (username_part, TEST_DOMAIN)

        self.assertEqual(username, ilsgateway_smsuser.username)
        self.assertEqual(first_name, ilsgateway_smsuser.first_name)
        self.assertEqual(last_name, ilsgateway_smsuser.last_name)
        self.assertEqual(smsuser.is_active, ilsgateway_smsuser.is_active)
        self.assertEqual(TEST_DOMAIN, ilsgateway_smsuser.get_domains()[0])
        self.assertEqual(smsuser.phone_numbers[0], ilsgateway_smsuser.default_phone_number)
