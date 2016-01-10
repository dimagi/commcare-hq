from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.api import SMSUser, ILSGatewayAPI
from custom.ilsgateway.tests.mock_endpoint import MockEndpoint
from custom.logistics.api import ApiSyncObject
from custom.logistics.commtrack import synchronization
from custom.logistics.models import MigrationCheckpoint

TEST_DOMAIN = 'ilsgateway-commtrack-smsusers-test'


class SMSUsersSyncTest(TestCase):

    def setUp(self):
        self.endpoint = MockEndpoint('http://test-api.com/', 'dummy', 'dummy')
        self.api_object = ILSGatewayAPI(TEST_DOMAIN, self.endpoint)
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)

        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

    def tearDown(self):
        for vn in VerifiedNumber.by_domain(TEST_DOMAIN):
            vn.delete()

    def test_create_smsuser(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)
        first_name, last_name = ilsgateway_smsuser.name.split(' ', 1)
        username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), smsuser.id)
        username = "%s@%s.commcarehq.org" % (username_part, TEST_DOMAIN)

        self.assertEqual(username, ilsgateway_smsuser.username)
        self.assertEqual(first_name, ilsgateway_smsuser.first_name)
        self.assertEqual(last_name, ilsgateway_smsuser.last_name)
        self.assertEqual(smsuser.is_active, str(ilsgateway_smsuser.is_active))
        self.assertEqual(TEST_DOMAIN, ilsgateway_smsuser.get_domains()[0])
        self.assertEqual(ilsgateway_smsuser.default_phone_number, '4224242442')
        verified_number = VerifiedNumber.by_phone(ilsgateway_smsuser.default_phone_number)
        self.assertIsNotNone(verified_number)
        self.assertIsNone(verified_number.backend_id)

    def test_create_smsuser_with_test_backend(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[1])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)
        first_name, last_name = ilsgateway_smsuser.name.split(' ', 1)
        username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), smsuser.id)
        username = "%s@%s.commcarehq.org" % (username_part, TEST_DOMAIN)

        self.assertEqual(username, ilsgateway_smsuser.username)
        self.assertEqual(first_name, ilsgateway_smsuser.first_name)
        self.assertEqual(last_name, ilsgateway_smsuser.last_name)
        self.assertEqual(smsuser.is_active, str(ilsgateway_smsuser.is_active))
        self.assertEqual(TEST_DOMAIN, ilsgateway_smsuser.get_domains()[0])
        self.assertEqual(ilsgateway_smsuser.default_phone_number, '222')
        verified_number = VerifiedNumber.by_phone(ilsgateway_smsuser.default_phone_number)
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.backend_id, 'MOBILE_BACKEND_TEST')

    def test_multiple_phone_numbers_migration(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[2])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)

        self.assertListEqual(ilsgateway_smsuser.phone_numbers, ['2222', '3333'])

    def test_phone_numbers_edit(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[2])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertListEqual(ilsgateway_smsuser.phone_numbers, ['2222', '3333'])
        vn1 = VerifiedNumber.by_phone('2222')
        vn2 = VerifiedNumber.by_phone('3333')
        self.assertIsNotNone(vn1)
        self.assertIsNotNone(vn2)

        smsuser.phone_numbers = smsuser.phone_numbers[:1]
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertListEqual(ilsgateway_smsuser.phone_numbers, ['2222'])
        vn1 = VerifiedNumber.by_phone('2222')
        vn2 = VerifiedNumber.by_phone('3333')
        self.assertIsNotNone(vn1)
        self.assertIsNone(vn2)

        smsuser.phone_numbers = []
        ilsgateway_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertListEqual(ilsgateway_smsuser.phone_numbers, [])
        vn1 = VerifiedNumber.by_phone('2222')
        vn2 = VerifiedNumber.by_phone('3333')
        self.assertIsNone(vn1)
        self.assertIsNone(vn2)

    def test_smsusers_migration(self):
        checkpoint = MigrationCheckpoint(
            domain=TEST_DOMAIN,
            start_date=datetime.utcnow(),
            date=datetime.utcnow(),
            api='product',
            limit=100,
            offset=0
        )
        sms_user_api = ApiSyncObject(
            'smsuser',
            self.endpoint.get_smsusers,
            self.api_object.sms_user_sync
        )
        synchronization(sms_user_api, checkpoint, None, 100, 0)
        self.assertEqual('smsuser', checkpoint.api)
        self.assertEqual(100, checkpoint.limit)
        self.assertEqual(0, checkpoint.offset)
        self.assertEqual(6, len(CommCareUser.by_domain(TEST_DOMAIN)))
