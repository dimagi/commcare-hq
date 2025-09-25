import uuid
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard.sms import MessagingSubEvent
from corehq.apps.sms.handlers.exceptions import KeywordProcessingError
from corehq.apps.sms.handlers.keyword import (
    _process_messaging_action,
    _resolve_action_contact,
    _resolve_case_for_user,
    _setup_messaging_event,
)
from corehq.apps.sms.models import SMS, Keyword, KeywordAction, MessagingEvent
from corehq.apps.users.models import CommCareUser


class BaseKeywordHelperTest(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super(BaseKeywordHelperTest, cls).setUpClass()

        factory = AppFactory(build_version='2.24.0')
        cls.app = factory.app
        module, form = factory.new_basic_module('basic', 'person')
        cls.app.add_module(module)

        cls.survey_keyword = Keyword.objects.create(domain=cls.domain, keyword="TEST")
        cls.msg = SMS(couch_recipient_doc_type="CommCareUser", couch_recipient="user123")
        cls.sender = CommCareUser.create(
            cls.domain, 'TestUser', "123", None, None,
        )

        cls.keyword_action = KeywordAction.objects.create(
            keyword=cls.survey_keyword,
            action=KeywordAction.ACTION_SMS,
            recipient=KeywordAction.RECIPIENT_SENDER,
            message_content="Test message",
            app_id=str(cls.app._id),
            form_unique_id=str(form.unique_id)
        )
        cls.verified_number = Mock(
            domain=cls.domain,
        )
        cls.mock_logged_event = Mock()
        cls.mock_logged_event.error = MagicMock()

        cls.case_factory = CaseFactory(domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.sender.delete(cls.domain, deleted_by=None)
        super(BaseKeywordHelperTest, cls).tearDownClass()


class TestSetupMessagingEvent(BaseKeywordHelperTest):
    def test_success(self):
        """Test successful setup of messaging event and subevent."""
        logged_event, subevent = _setup_messaging_event(
            self.survey_keyword, self.sender, self.msg
        )
        assert MessagingEvent.objects.all().count() == 1
        assert MessagingSubEvent.objects.all().count() == 1
        assert MessagingEvent.objects.get(domain=self.domain) == logged_event
        assert MessagingSubEvent.objects.get(domain=self.domain) == subevent


class TestResolveCaseForUser(BaseKeywordHelperTest):

    @patch('corehq.apps.sms.handlers.keyword.keyword_uses_form_that_requires_case', return_value=True)
    def test_success(self, mock_keyword_uses_form):
        external_id = uuid.uuid4().hex
        test_case = self.case_factory.create_case(
            case_type='foobar',
            owner_id=self.sender.get_id,
            case_name='test',
            external_id=external_id,
        )
        case, args = _resolve_case_for_user(
            self.sender,
            self.survey_keyword,
            args=["keyword", external_id, 'arg1'],
            verified_number=self.verified_number,
            logged_event=self.mock_logged_event
        )
        assert test_case == case
        assert args == ['arg1']

    def test_no_keywords(self):
        case, args = _resolve_case_for_user(
            self.sender,
            self.survey_keyword,
            args=["keyword", "arg1", "arg2"],
            verified_number=self.verified_number,
            logged_event=self.mock_logged_event
        )
        assert case is None
        assert args == ["arg1", "arg2"]

    @patch("corehq.apps.sms.handlers.keyword.send_keyword_response")
    @patch('corehq.apps.sms.handlers.keyword.keyword_uses_form_that_requires_case', return_value=True)
    def test_single_arg(self, mock_keyword_uses_form, mock_send_response):
        with self.assertRaises(KeywordProcessingError) as error:
            _resolve_case_for_user(
                self.sender,
                self.survey_keyword,
                args=["keyword"],
                verified_number=self.verified_number,
                logged_event=self.mock_logged_event
            )
        assert str(error.exception) == "Missing external ID"

    @patch("corehq.apps.sms.handlers.keyword.send_keyword_response")
    @patch('corehq.apps.sms.handlers.keyword.keyword_uses_form_that_requires_case', return_value=True)
    def test_no_matches(self, mock_keyword_uses_form, mock_send_response):
        with self.assertRaises(KeywordProcessingError) as error:
            _resolve_case_for_user(
                self.sender,
                self.survey_keyword,
                args=["keyword", "123"],
                verified_number=self.verified_number,
                logged_event=self.mock_logged_event
            )
        assert str(error.exception) == "Case not found"

    @patch("corehq.apps.sms.handlers.keyword.send_keyword_response")
    @patch('corehq.apps.sms.handlers.keyword.keyword_uses_form_that_requires_case', return_value=True)
    def test_multiple_matches(self, mock_keyword_uses_form, mock_send_response):
        external_id = uuid.uuid4().hex
        for i in range(2):
            self.case_factory.create_case(
                case_type='foobar',
                owner_id=self.sender.get_id,
                case_name=f'test{i}',
                external_id=external_id,
            )

        with self.assertRaises(KeywordProcessingError) as error:
            _resolve_case_for_user(
                self.sender,
                self.survey_keyword,
                args=["keyword", external_id],
                verified_number=self.verified_number,
                logged_event=self.mock_logged_event
            )
        assert str(error.exception) == "Multiple cases found"


class TestResolveActionContact(BaseKeywordHelperTest):

    def test_recipint_sender(self):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_SMS,
            recipient=KeywordAction.RECIPIENT_SENDER,
        )
        contact = _resolve_action_contact(kw_action, self.sender, self.verified_number)
        assert contact == self.sender

    def test_recipient_owner(self):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_SMS,
            recipient=KeywordAction.RECIPIENT_OWNER,
        )

        # Sender is not CommCareCase
        contact = _resolve_action_contact(kw_action, self.sender, self.verified_number)
        assert contact is None

        # Sender is CommCareCase
        test_case = self.case_factory.create_case(
            case_type='foobar',
            owner_id=self.sender.get_id,
            case_name='test',
        )
        contact = _resolve_action_contact(kw_action, test_case, self.verified_number)
        assert contact.get_id == self.sender.get_id

    def test_recipient_group(self):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_SMS,
            recipient=KeywordAction.RECIPIENT_USER_GROUP,
        )

        # No group
        contact = _resolve_action_contact(kw_action, self.sender, self.verified_number)
        assert contact is None

        # Valid group
        group = Group(domain=self.domain, name="G1", users=[self.sender.get_id])
        group.save()
        kw_action.recipient_id = group.get_id
        contact = _resolve_action_contact(kw_action, self.sender, self.verified_number)
        assert contact.get_id == group.get_id

    def test_unknown_recipient(self):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_SMS,
            recipient='Unknown',
        )
        contact = _resolve_action_contact(kw_action, self.sender, self.verified_number)
        assert contact is None


class TestProcessMessagingAction(BaseKeywordHelperTest):

    @classmethod
    def setUpClass(cls):
        super(TestProcessMessagingAction, cls).setUpClass()

        cls.test_case = cls.case_factory.create_case(
            case_type='foobar',
            owner_id=cls.sender.get_id,
            case_name='test',
        )

    def _call_func(self, kw_action):
        _process_messaging_action(
            kw_action,
            contact=self.sender,
            case=self.test_case,
            verified_number=self.verified_number,
            logged_event=self.mock_logged_event
        )

    def test_unexpected_action(self):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action='Unknown',
            recipient=KeywordAction.RECIPIENT_SENDER,
        )

        with self.assertRaises(ValueError) as error:
            self._call_func(kw_action)
        assert str(error.exception) == "Unexpected action Unknown"

    @patch('corehq.messaging.scheduling.models.content.SMSContent.send')
    def test_sms_message(self, mock_send):
        self._call_func(self.keyword_action)
        mock_send.assert_called_once_with(
            self.sender,
            self.mock_logged_event,
            phone_entry=self.verified_number,
        )

    @patch('corehq.messaging.scheduling.models.content.SMSSurveyContent.send')
    def test_sms_survey(self, mock_send):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_SMS_SURVEY,
            recipient=KeywordAction.RECIPIENT_OWNER,
        )
        self._call_func(kw_action)
        mock_send.assert_called_once_with(
            self.sender,
            self.mock_logged_event,
            phone_entry=None,
        )

    @patch('corehq.messaging.scheduling.models.content.ConnectMessageContent.send')
    def test_connect_message(self, mock_send):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_CONNECT_MESSAGE,
            recipient=KeywordAction.RECIPIENT_SENDER,
        )
        self._call_func(kw_action)
        mock_send.assert_called_once_with(
            self.sender,
            self.mock_logged_event,
            phone_entry=self.verified_number,
        )

    @patch('corehq.messaging.scheduling.models.content.ConnectMessageSurveyContent.send')
    def test_connect_survey(self, mock_send):
        kw_action = KeywordAction(
            keyword=self.survey_keyword,
            action=KeywordAction.ACTION_CONNECT_SURVEY,
            recipient=KeywordAction.RECIPIENT_SENDER,
        )
        self._call_func(kw_action)
        mock_send.assert_called_once_with(
            self.sender,
            self.mock_logged_event,
            phone_entry=self.verified_number,
        )
