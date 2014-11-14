from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.api import SMSUser
from custom.ilsgateway.commtrack import sync_ilsgateway_smsuser, smsusers_sync
from custom.ilsgateway.models import LogisticsMigrationCheckpoint

TEST_DOMAIN = 'ilsgateway-commtrack-smsusers-test'


class SMSUsersSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)

        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_smsuser(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = sync_ilsgateway_smsuser(TEST_DOMAIN, smsuser)
        first_name, last_name = ilsgateway_smsuser.name.split(' ', 1)
        username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), smsuser.id)
        username = "%s@%s.commcarehq.org" % (username_part, TEST_DOMAIN)

        self.assertEqual(username, ilsgateway_smsuser.username)
        self.assertEqual(first_name, ilsgateway_smsuser.first_name)
        self.assertEqual(last_name, ilsgateway_smsuser.last_name)
        self.assertEqual(smsuser.is_active, str(ilsgateway_smsuser.is_active))
        self.assertEqual(TEST_DOMAIN, ilsgateway_smsuser.get_domains()[0])
        self.assertEqual(smsuser.phone_numbers[0], ilsgateway_smsuser.default_phone_number)

    def test_smsusers_migration(self):
        from custom.ilsgateway.tests import MockEndpoint
        checkpoint = LogisticsMigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.now(),
            date=datetime.now(),
            api='product',
            limit=1000,
            offset=0
        )
        smsusers_sync(TEST_DOMAIN, MockEndpoint('http://test-api.com/', 'dummy', 'dummy'), checkpoint, limit=1000,
                      offset=0)
        self.assertEqual('smsuser', checkpoint.api)
        self.assertEqual(1000, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(6, len(CommCareUser.by_domain(TEST_DOMAIN)))
