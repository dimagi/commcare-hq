import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.sms.mixin import VerifiedNumber
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
        self.api_object.create_or_edit_roles()
        for user in CommCareUser.by_domain(TEST_DOMAIN):
            user.delete()

        for verified_number in VerifiedNumber.by_domain(TEST_DOMAIN):
            verified_number.delete()

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
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '2222222222')
        domain_name = ewsghana_smsuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
        self.assertIsInstance(ewsghana_smsuser.user_data['role'], list)
        self.assertEqual(len(ewsghana_smsuser.user_data['role']), 1)
        self.assertEqual(ewsghana_smsuser.user_data['role'][0], 'Other')

    def test_edit_smsuser(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        user_id = ewsghana_smsuser.get_id
        self.assertIsNotNone(user_id)
        smsuser.phone_numbers = ['111111111']
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertEqual(user_id, ewsghana_smsuser.get_id)
        self.assertEqual(ewsghana_smsuser.default_phone_number, '111111111')
        self.assertListEqual(ewsghana_smsuser.phone_numbers, ['111111111'])
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '111111111')

    def test_edit_phone_number1(self):
        """
        When phone number is deleted on EWS side it also should be deleted in HQ
        :return:
        """
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])

        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        smsuser.phone_numbers = []
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertIsNone(ewsghana_smsuser.default_phone_number)
        self.assertListEqual(ewsghana_smsuser.phone_numbers, [])
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNone(verified_number)

    def test_edit_phone_number2(self):
        """
        When phone number is added on EWS side it also should be added in HQ
        """
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])
        smsuser.phone_numbers = []
        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNone(verified_number)
        smsuser.phone_numbers = ['111111111']
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertIsNotNone(ewsghana_smsuser.default_phone_number)
        self.assertListEqual(ewsghana_smsuser.phone_numbers, ['111111111'])
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '111111111')

    def test_edit_phone_number3(self):
        """
        When phone number is edited on EWS side it also should be edited in HQ
        """
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])
        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '2222222222')
        smsuser.phone_numbers = ['111111111']
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        self.assertIsNotNone(ewsghana_smsuser.default_phone_number)
        self.assertListEqual(ewsghana_smsuser.phone_numbers, ['111111111'])
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '111111111')

    def test_edit_phone_number4(self):
        """
            Number shouldn't be changed when is not edited on EWS side.
        """
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])
        self.assertEqual(0, len(CommCareUser.by_domain(TEST_DOMAIN)))
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '2222222222')
        ewsghana_smsuser = self.api_object.sms_user_sync(smsuser)
        verified_number = ewsghana_smsuser.get_verified_number()
        self.assertIsNotNone(verified_number)
        self.assertEqual(verified_number.phone_number, '2222222222')
