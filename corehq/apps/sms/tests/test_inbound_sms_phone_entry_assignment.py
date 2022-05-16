import uuid

from django.test import TestCase

from corehq.apps.sms.api import get_inbound_phone_entry_from_sms
from corehq.apps.sms.models import PhoneNumber, MobileBackendInvitation, SMS, SQLMobileBackend
from corehq.apps.smsforms.models import XFormsSessionSynchronization, SMSChannel, RunningSessionInfo
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.util.test_utils import flag_enabled


class TestGetInboundPhoneEntry(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.domain1_name = uuid.uuid4().hex
        cls.domain2_name = uuid.uuid4().hex

        cls.global_backend = SQLTestSMSBackend.objects.create(
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            is_global=True,
            name='GLOBAL'
        )

        cls.domain1_backend = SQLTestSMSBackend.objects.create(
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            is_global=False,
            domain=cls.domain1_name,
            name='BACKEND1'
        )

        MobileBackendInvitation.objects.create(
            domain=cls.domain2_name,
            backend=cls.domain1_backend,
            accepted=True
        )

        cls.domain2_backend = SQLTestSMSBackend.objects.create(
            hq_api_id=SQLTestSMSBackend.get_api_id(),
            is_global=False,
            domain=cls.domain2_name,
            name='BACKEND2'
        )

        cls.phone_number = '01112223333'
        cls.number1_domain1 = PhoneNumber.objects.create(
            domain=cls.domain1_name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-1',
            phone_number=cls.phone_number,
            verified=True,
            is_two_way=True,
            pending_verification=False
        )
        cls.number2_domain1 = PhoneNumber.objects.create(
            domain=cls.domain1_name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-2',
            phone_number=cls.phone_number,
            verified=True,
            is_two_way=False,
            pending_verification=False
        )
        cls.number3_domain2 = PhoneNumber.objects.create(
            domain=cls.domain2_name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-3',
            phone_number=cls.phone_number,
            verified=True,
            is_two_way=False,
            pending_verification=False
        )
        cls.number4_domain2 = PhoneNumber.objects.create(
            domain=cls.domain2_name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-4',
            phone_number=cls.phone_number,
            verified=True,
            is_two_way=False,
            pending_verification=False
        )

        for number in [cls.number1_domain1, cls.number2_domain1, cls.number3_domain2]:
            number._clear_caches()

        SQLMobileBackend.load.clear(SQLMobileBackend, cls.global_backend.couch_id, is_couch_id=True)
        SQLMobileBackend.load.clear(SQLMobileBackend, cls.domain1_backend.couch_id, is_couch_id=True)
        SQLMobileBackend.load.clear(SQLMobileBackend, cls.domain2_backend.couch_id, is_couch_id=True)

    def test_get_reserved_number(self):
        """Should return the only 'two way' enabled number"""
        number = PhoneNumber.get_reserved_number(self.phone_number)
        self.assertTrue(number.is_two_way)
        self.assertEqual(number.owner_id, "fake-owner-1")

    def test_get_two_way_number_with_domain_scope(self):
        number = PhoneNumber.get_two_way_number_with_domain_scope(
            self.phone_number, [self.domain1_name, self.domain2_name])
        self.assertEqual(number.owner_id, "fake-owner-1")

    def test_get_two_way_number_with_domain_scope__reduced_scope(self):
        number = PhoneNumber.get_two_way_number_with_domain_scope(
            self.phone_number, [self.domain2_name])
        self.assertEqual(number.owner_id, "fake-owner-3")

    def test_get_inbound_phone_entry__no_backend_id(self):
        sms = SMS(phone_number=self.phone_number)
        phone_number, has_domain_two_way_scope = get_inbound_phone_entry_from_sms(sms)

        self.assertEqual(phone_number.owner_id, "fake-owner-1")
        self.assertFalse(has_domain_two_way_scope)

    def test_get_inbound_phone_entry__global_backend(self):
        sms = SMS(phone_number=self.phone_number, backend_id=self.global_backend.couch_id)
        phone_number, has_domain_two_way_scope = get_inbound_phone_entry_from_sms(sms)

        self.assertEqual(phone_number.owner_id, "fake-owner-1")
        self.assertFalse(has_domain_two_way_scope)
        self.assertTrue(self.global_backend.domain_is_authorized(phone_number.domain))

    def _get_inbound_phone_entry__backend_domain_2(self):
        """The utilities main objective is to ensure consistency between the various
        test methods that are testing `get_inbound_phone_entry` under different conditions
        """
        sms = SMS(phone_number=self.phone_number, backend_id=self.domain2_backend.couch_id)
        return get_inbound_phone_entry_from_sms(sms)

    def test_get_inbound_phone_entry__domain_backend(self):
        """Should return the only 'two way' number.
        Note that the backend 'belongs' to domain2 but the contact returned is from domain1.
        This means that the message is ultimately associated with domain1.
        TODO: determine if this should be allowed"""
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()

        self.assertEqual(phone_number.owner_id, "fake-owner-1")
        self.assertFalse(has_domain_two_way_scope)
        self.assertFalse(self.domain2_backend.domain_is_authorized(phone_number.domain))  # bad

    def test_get_inbound_phone_entry__inbound_sms_leniency_off(self):
        """Same as `test_get_inbound_phone_entry__domain_backend`"""
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()
        self.assertEqual(phone_number.owner_id, "fake-owner-1")
        self.assertFalse(has_domain_two_way_scope)
        self.assertFalse(self.domain2_backend.domain_is_authorized(phone_number.domain))  # bad

    @flag_enabled("INBOUND_SMS_LENIENCY")
    def test_get_inbound_phone_entry__inbound_sms_leniency_on(self):
        """Should return a phone number in a domain of the backend"""
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()
        self.assertEqual(phone_number.owner_id, "fake-owner-3")
        self.assertTrue(has_domain_two_way_scope)
        self.assertTrue(self.domain2_backend.domain_is_authorized(phone_number.domain))

    @flag_enabled("INBOUND_SMS_LENIENCY")
    def test_get_inbound_phone_entry__one_phone_number_multiple_contacts_off(self):
        """Same as 'inbound_sms_leniency'"""
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()
        self.assertEqual(phone_number.owner_id, "fake-owner-3")
        self.assertTrue(has_domain_two_way_scope)
        self.assertTrue(self.domain2_backend.domain_is_authorized(phone_number.domain))

    @flag_enabled("INBOUND_SMS_LENIENCY")
    @flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
    def test_get_inbound_phone_entry__one_phone_number_multiple_contacts_on__no_session(self):
        """With no session this should fall back to the 'lenient sms' functionality"""
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()

        self.assertEqual(phone_number.owner_id, "fake-owner-3")
        self.assertTrue(has_domain_two_way_scope)
        self.assertTrue(self.domain2_backend.domain_is_authorized(phone_number.domain))

    @flag_enabled("INBOUND_SMS_LENIENCY")
    @flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
    def test_get_inbound_phone_entry__one_phone_number_multiple_contacts_on__with_session(self):
        """Should return the phone number of the contact associated with the session"""
        channel = SMSChannel(self.domain2_backend.couch_id, self.phone_number)
        info = RunningSessionInfo(uuid.uuid4().hex, "fake-owner-4")
        XFormsSessionSynchronization._set_running_session_info_for_channel(channel, info, 60)
        self.addCleanup(XFormsSessionSynchronization._release_running_session_info_for_channel, info, channel)
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()

        self.assertEqual(phone_number.owner_id, "fake-owner-4")
        self.assertTrue(has_domain_two_way_scope)
        self.assertTrue(self.domain2_backend.domain_is_authorized(phone_number.domain))

    @flag_enabled("INBOUND_SMS_LENIENCY")
    @flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
    def test_get_inbound_phone_entry__one_phone_number_multiple_contacts_on__session_different_domain(self):
        """Phone number returned belongs to a domain which does not have access to this backend.
        TODO: This should probably be an error or it should fall back to 'lenient' query"""
        channel = SMSChannel(self.domain2_backend.couch_id, self.phone_number)
        info = RunningSessionInfo(uuid.uuid4().hex, "fake-owner-2")
        XFormsSessionSynchronization._set_running_session_info_for_channel(channel, info, 60)
        self.addCleanup(XFormsSessionSynchronization._release_running_session_info_for_channel, info, channel)
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()

        self.assertEqual(phone_number.owner_id, "fake-owner-2")
        self.assertTrue(has_domain_two_way_scope)
        self.assertFalse(self.domain2_backend.domain_is_authorized(phone_number.domain))  # bad

    @flag_enabled("INBOUND_SMS_LENIENCY")
    @flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
    def test_get_inbound_phone_entry__one_phone_number_multiple_contacts_on__session_no_contact(self):
        """Fall back to lenient query if we can't find the contact returned by the sticky session"""
        channel = SMSChannel(self.domain2_backend.couch_id, self.phone_number)
        info = RunningSessionInfo(None, "fake-owner-missing")
        XFormsSessionSynchronization._set_running_session_info_for_channel(channel, info, 60)
        self.addCleanup(XFormsSessionSynchronization._release_running_session_info_for_channel, info, channel)
        phone_number, has_domain_two_way_scope = self._get_inbound_phone_entry__backend_domain_2()

        self.assertEqual(phone_number.owner_id, "fake-owner-3")
        self.assertTrue(has_domain_two_way_scope)
        self.assertTrue(self.domain2_backend.domain_is_authorized(phone_number.domain))
