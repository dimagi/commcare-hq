import uuid

from django.test import TestCase

from mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.formplayer_api.smsforms.api import (
    TouchformsError,
    XformsResponse,
)
from corehq.apps.formplayer_api.smsforms.sms import SessionStartInfo
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCaseSQL


@patch('corehq.apps.smsforms.app.tfsms.start_session')
class TestStartSession(TestCase):
    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        cls.factory = AppFactory(domain=cls.domain)
        cls.app = cls.factory.app
        cls.module, cls.basic_form = cls.factory.new_basic_module('basic', 'patient')

        # necessary to render_xform
        builder = XFormBuilder(cls.basic_form.name)
        builder.new_question(name='name', label='Name')
        cls.basic_form.source = builder.tostring(pretty_print=True).decode('utf-8')

        cls.phone_number = "+919999999999"
        cls.case_id = uuid.uuid4().hex
        cls.recipient = None

        cls.case = CommCareCaseSQL(domain=cls.domain, case_id=cls.case_id, case_json={'language_code': 'fr'})
        cls.web_user = WebUser(username='web-user@example.com', _id=uuid.uuid4().hex, language='hin')

    @classmethod
    def tearDownClass(cls):
        SQLXFormsSession.objects.all().delete()

    def _start_session(self, yield_responses=False):
        if not self.recipient:
            raise Exception("Set recipient")
        return start_session(
            SQLXFormsSession.create_session_object(
                self.domain,
                self.recipient,
                self.phone_number,
                self.app,
                self.basic_form,
            ),
            self.domain,
            self.recipient,
            self.app,
            self.basic_form,
            yield_responses=yield_responses
        )

    def _mock_xform_response(self, tfsms_start_session_mock, status, additional_response=None):
        response_dict = {
            'session_id': uuid.uuid4().hex,
            'status': status
        }
        if additional_response:
            response_dict.update(additional_response)
        xform_response = XformsResponse(response_dict)
        tfsms_start_session_mock.return_value = SessionStartInfo(
            xform_response,
            self.domain
        )
        return xform_response

    @patch('corehq.apps.smsforms.app.XFormsConfig')
    def test_start_session_as_case(self, xform_config_mock, tfsms_start_session_mock):
        self.recipient = self.case

        event_response = {'output': 'result', 'type': 'question'}  # move to next question
        xform_response = self._mock_xform_response(tfsms_start_session_mock, status='success',
                                                   additional_response={'event': event_response})

        session, responses = self._start_session(yield_responses=True)

        expected_session_data = {
            'device_id': 'commconnect', 'app_version': '2.0', 'domain': self.domain,
            'username': self.recipient.raw_username, 'user_id': self.recipient.get_id,
            'user_data': {},
            'app_id': None
        }
        xform_config_mock.assert_called_once_with(
            form_content=self.basic_form.render_xform().decode('utf-8'),
            language=self.recipient.get_language_code(),
            session_data=expected_session_data,
            domain=self.domain,
            restore_as_case_id=self.recipient.case_id
        )

        self.assertEqual(session.session_id, xform_response.session_id)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0], xform_response)

    @patch('corehq.apps.smsforms.app.XFormsConfig')
    def test_start_session_as_user(self, xform_config_mock, tfsms_start_session_mock):
        self.recipient = self.web_user

        xform_response = self._mock_xform_response(tfsms_start_session_mock, status="validation-error")

        session, responses = self._start_session(yield_responses=True)

        expected_session_data = {
            'device_id': 'commconnect', 'app_version': '2.0', 'domain': self.domain,
            'username': self.recipient.raw_username, 'user_id': self.recipient.get_id,
            'user_data': {
                'commcare_first_name': None,
                'commcare_last_name': None,
                'commcare_phone_number': None,
                'commcare_project': self.domain,
            },
            'app_id': None
        }
        xform_config_mock.assert_called_once_with(
            form_content=self.basic_form.render_xform().decode('utf-8'),
            language=self.recipient.get_language_code(),
            session_data=expected_session_data,
            domain=self.domain,
            restore_as=self.recipient.raw_username
        )

        self.assertEqual(session.session_id, xform_response.session_id)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0], xform_response)

    def test_http_error(self, tfsms_start_session_mock):
        self.recipient = self.case

        xform_response = self._mock_xform_response(tfsms_start_session_mock, status='http-error')

        with self.assertRaisesMessage(TouchformsError, 'Cannot connect to touchforms.'):
            self._start_session()

        session = SQLXFormsSession.objects.first()
        self.assertFalse(session.completed)
        self.assertEqual(session.session_id, xform_response.session_id)

    def test_text_responses(self, tfsms_start_session_mock):
        self.recipient = self.case

        self._mock_xform_response(tfsms_start_session_mock, status="validation-error",
                                  additional_response={'reason': 'human-error'})

        session, responses = self._start_session(yield_responses=False)

        self.assertEqual(responses, ["human-error"])
