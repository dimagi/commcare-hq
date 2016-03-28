from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, SQLLastReadMessage, OUTGOING, INCOMING
from corehq.apps.sms.views import ChatMessageHistory
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import set_case_property_directly
from corehq.util.test_utils import softer_assert
from datetime import datetime
from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from mock import patch


class LastReadMessageTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'sms-chat-test-domain'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()

    def test_last_read_message(self):
        self.assertIsNone(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'))
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'))
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'))

        lrm1 = SQLLastReadMessage.objects.create(
            domain=self.domain,
            read_by='user-id-1',
            contact_id='contact-id-1',
            message_id='message-id-1',
            message_timestamp=datetime(2016, 2, 17, 12, 0),
        )
        self.addCleanup(lrm1.delete)

        self.assertEqual(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'), lrm1)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'), lrm1)
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'))

        lrm2 = SQLLastReadMessage.objects.create(
            domain=self.domain,
            read_by='user-id-2',
            contact_id='contact-id-1',
            message_id='message-id-2',
            message_timestamp=datetime(2016, 2, 17, 13, 0),
        )
        self.addCleanup(lrm2.delete)

        self.assertEqual(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'), lrm2)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'), lrm1)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'), lrm2)


class ChatHistoryTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'sms-chat-history-test-domain'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        cls.contact1 = CommCareCase(domain=cls.domain, name='test-case')
        set_case_property_directly(cls.contact1, 'custom_name', 'custom-name')
        cls.contact1.save()

        cls.contact2 = CommCareCase(domain='another-domain')
        cls.contact2.save()

        cls.contact3 = CommCareUser.create(cls.domain, 'user1', '123')

        cls.chat_user = CommCareUser.create(cls.domain, 'user2', '123')
        cls.chat_user.first_name = 'Sam'
        cls.chat_user.save()

        cls.outgoing_from_system = SMS.objects.create(
            domain=cls.domain,
            direction=OUTGOING,
            date=datetime(2016, 2, 18, 0, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='Remember your appointment tomorrow',
            chat_user_id=None,
            processed=True,
            xforms_session_couch_id=None,
            invalid_survey_response=False,
        )

        cls.outgoing_not_processed = SMS.objects.create(
            domain=cls.domain,
            direction=OUTGOING,
            date=datetime(2016, 2, 18, 1, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='Remember your appointment next week',
            chat_user_id=None,
            processed=False,
            xforms_session_couch_id=None,
            invalid_survey_response=False,
        )

        cls.outgoing_from_chat = SMS.objects.create(
            domain=cls.domain,
            direction=OUTGOING,
            date=datetime(2016, 2, 18, 2, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='How are you?',
            chat_user_id=cls.chat_user.get_id,
            processed=True,
            xforms_session_couch_id=None,
            invalid_survey_response=False,
        )

        cls.incoming_not_processed = SMS.objects.create(
            domain=cls.domain,
            direction=INCOMING,
            date=datetime(2016, 2, 18, 3, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='Good',
            chat_user_id=None,
            processed=False,
            xforms_session_couch_id=None,
            invalid_survey_response=False,
        )

        cls.incoming_survey_answer1 = SMS.objects.create(
            domain=cls.domain,
            direction=INCOMING,
            date=datetime(2016, 2, 18, 4, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='x',
            chat_user_id=None,
            processed=True,
            xforms_session_couch_id='session-id',
            invalid_survey_response=True,
        )

        cls.outgoing_survey_response1 = SMS.objects.create(
            domain=cls.domain,
            direction=OUTGOING,
            date=datetime(2016, 2, 18, 5, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='Invalid Response',
            chat_user_id=None,
            processed=True,
            xforms_session_couch_id='session-id',
            invalid_survey_response=True,
        )

        cls.incoming_survey_answer2 = SMS.objects.create(
            domain=cls.domain,
            direction=INCOMING,
            date=datetime(2016, 2, 18, 6, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='1',
            chat_user_id=None,
            processed=True,
            xforms_session_couch_id='session-id',
            invalid_survey_response=False,
        )

        cls.outgoing_survey_response2 = SMS.objects.create(
            domain=cls.domain,
            direction=OUTGOING,
            date=datetime(2016, 2, 18, 7, 0),
            couch_recipient_doc_type=cls.contact1.doc_type,
            couch_recipient=cls.contact1.get_id,
            text='Thank you for completing the survey',
            chat_user_id=None,
            processed=True,
            xforms_session_couch_id='session-id',
            invalid_survey_response=False,
        )

    @property
    def new_view(self):
        view = ChatMessageHistory()
        view.args = [self.domain]
        view.kwargs = {}
        return view

    @classmethod
    def tearDownClass(cls):
        cls.contact1.delete()
        cls.contact2.delete()
        cls.contact3.delete()
        cls.chat_user.delete()
        cls.domain_obj.delete()

    def patch_contact_id(self, contact_id):
        return patch('corehq.apps.sms.views.ChatMessageHistory.contact_id', contact_id)

    def patch_start_date(self, start_date):
        return patch('corehq.apps.sms.views.ChatMessageHistory.start_date_str', start_date)

    @classmethod
    def set_custom_case_username(cls, name):
        cls.domain_obj.custom_case_username = name
        cls.domain_obj.save()

    @classmethod
    def set_survey_filter_option(cls, filter_surveys_from_chat,
            show_invalid_survey_responses_in_chat):
        cls.domain_obj.filter_surveys_from_chat = filter_surveys_from_chat
        cls.domain_obj.show_invalid_survey_responses_in_chat = show_invalid_survey_responses_in_chat
        cls.domain_obj.save()

    def test_contact(self):
        with self.patch_contact_id(self.contact1.get_id):
            self.assertEqual(self.new_view.contact.get_id, self.contact1.get_id)

        with self.patch_contact_id(self.contact2.get_id):
            self.assertIsNone(self.new_view.contact)

    def test_contact_name(self):
        self.set_custom_case_username(None)
        with self.patch_contact_id(self.contact1.get_id):
            self.assertEqual(self.new_view.contact_name, 'test-case')

        self.set_custom_case_username('custom_name')
        with self.patch_contact_id(self.contact1.get_id):
            self.assertEqual(self.new_view.contact_name, 'custom-name')

        with self.patch_contact_id(self.contact3.get_id):
            self.assertEqual(self.new_view.contact_name, 'user1')

        self.set_custom_case_username(None)

    def test_get_chat_user_name(self):
        self.assertEqual(
            self.new_view.get_chat_user_name(self.chat_user.get_id),
            'Sam'
        )
        self.assertEqual(
            self.new_view.get_chat_user_name(None),
            'System'
        )
        self.assertEqual(
            self.new_view.get_chat_user_name('fake-user-id'),
            'Unknown'
        )

    @softer_assert
    def test_start_date(self):
        with self.patch_start_date(None):
            self.assertIsNone(self.new_view.start_date)

        with self.patch_start_date('bad-date-format'):
            self.assertIsNone(self.new_view.start_date)

        with self.patch_start_date('2016-02-18T20:42:30.175083Z'):
            self.assertEqual(self.new_view.start_date, datetime(2016, 2, 18, 20, 42, 30, 175083))

    def sms_to_json(self, sms):
        """
        Note: This method is very specific to the data of this test and
        assumes that:
            - the recipient is always self.contact1
            - chat_user_id always points to self.chat_user if present
            - the user requesting the chat history is always self.chat_user
        """
        if sms.direction == INCOMING:
            sender = 'test-case'
        else:
            if sms.chat_user_id:
                sender = 'Sam'
            else:
                sender = 'System'

        return {
            'sender': sender,
            'text': sms.text,
            'timestamp': sms.date.strftime("%I:%M%p %m/%d/%y").lower(),
            'utc_timestamp': json_format_datetime(sms.date),
            'sent_by_requester': sms.chat_user_id is not None,
        }

    def assertChatHistoryResponse(self, expected_data):
        actual_data, actual_last_sms = self.new_view.get_response_data(self.chat_user.get_id)
        expected_last_sms = expected_data[-1] if expected_data else None
        expected_data = sorted(expected_data, key=lambda sms: sms.date)
        expected_data = [self.sms_to_json(sms) for sms in expected_data]

        self.assertEqual(actual_data, expected_data)
        self.assertEqual(actual_last_sms, expected_last_sms)

    @classmethod
    def get_last_read_message(cls):
        return SQLLastReadMessage.by_user(cls.domain, cls.chat_user.get_id, cls.contact1.get_id)

    @classmethod
    def get_last_read_message_count(cls):
        return SQLLastReadMessage.objects.filter(domain=cls.domain).count()

    def assertLastReadMessage(self, sms):
        lrm = self.get_last_read_message()
        self.assertEqual(lrm.message_id, sms.couch_id)
        self.assertEqual(lrm.message_timestamp, sms.date)

    def test_get_response_data(self):
        with self.patch_contact_id(self.contact1.get_id):

            with self.patch_start_date(None):
                self.set_survey_filter_option(False, False)
                self.assertChatHistoryResponse([
                    self.outgoing_from_system,
                    self.outgoing_from_chat,
                    self.incoming_not_processed,
                    self.incoming_survey_answer1,
                    self.outgoing_survey_response1,
                    self.incoming_survey_answer2,
                    self.outgoing_survey_response2,
                ])

            with self.patch_start_date('2016-02-18T03:00:00.000000Z'):
                self.assertChatHistoryResponse([
                    self.incoming_survey_answer1,
                    self.outgoing_survey_response1,
                    self.incoming_survey_answer2,
                    self.outgoing_survey_response2,
                ])

            with self.patch_start_date('2016-02-18T07:00:00.000000Z'):
                self.assertChatHistoryResponse([])

            with self.patch_start_date(None):
                self.set_survey_filter_option(True, False)
                self.assertChatHistoryResponse([
                    self.outgoing_from_system,
                    self.outgoing_from_chat,
                    self.incoming_not_processed,
                ])

            with self.patch_start_date(None):
                self.set_survey_filter_option(True, True)
                self.assertChatHistoryResponse([
                    self.outgoing_from_system,
                    self.outgoing_from_chat,
                    self.incoming_not_processed,
                    self.incoming_survey_answer1,
                ])

            self.set_survey_filter_option(False, False)

    def test_update_last_read_message(self):
        self.assertEqual(self.get_last_read_message_count(), 0)

        with self.patch_contact_id(self.contact1.get_id):
            self.new_view.update_last_read_message(self.chat_user.get_id, self.outgoing_from_system)
            self.assertEqual(self.get_last_read_message_count(), 1)
            self.assertLastReadMessage(self.outgoing_from_system)

            self.new_view.update_last_read_message(self.chat_user.get_id, self.outgoing_from_chat)
            self.assertEqual(self.get_last_read_message_count(), 1)
            self.assertLastReadMessage(self.outgoing_from_chat)
