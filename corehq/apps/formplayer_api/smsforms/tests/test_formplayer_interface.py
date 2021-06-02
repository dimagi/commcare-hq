import requests_mock
from django.test import SimpleTestCase

from corehq.apps.formplayer_api.smsforms.api import FormplayerInterface
from corehq.apps.formplayer_api.utils import get_formplayer_url

SESSION_ID = "SESSION_ID"
DOMAIN = "smsforms_domain"
USER_ID = "USER_ID"

QUESTION_RESPONSE = {
    "event": {
        "datatype": "select",
        "choices": ["red", "green", "blue"],
        "caption": "What's your favorite color?",
        "type": "question",
        "answer": None,
        "required": 0,
        "ix": "1",
        "help": None
    }
}


class FormplayerInterfaceTests(SimpleTestCase):
    interface = FormplayerInterface(SESSION_ID, DOMAIN, USER_ID)

    def test_get_raw_instance(self):
        action = 'get-instance'
        with MockFormplayerRequest(action, {}) as mocker:
            self.interface.get_raw_instance()

        mocker.assert_exactly_one_request()
        request = mocker.get_last_request()

        expected_request_data = {
            'action': action,
            'session-id': SESSION_ID,
            'session_id': SESSION_ID,
            'domain': DOMAIN,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }
        self.validate_request(request, expected_request_data)

    def test_answer_question(self):
        action = 'answer'
        with MockFormplayerRequest(action, QUESTION_RESPONSE) as mocker:
            self.interface.answer_question("answer1")

        mocker.assert_exactly_one_request()
        request = mocker.get_last_request()

        expected_request_data = {
            'action': action,
            'answer': 'answer1',
            'session-id': SESSION_ID,
            'session_id': SESSION_ID,
            'domain': DOMAIN,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }
        self.validate_request(request, expected_request_data)

    def test_current_question(self):
        action = 'current'
        with MockFormplayerRequest(action, QUESTION_RESPONSE) as mocker:
            self.interface.current_question()

        mocker.assert_exactly_one_request()
        request = mocker.get_last_request()

        expected_request_data = {
            'action': action,
            'session-id': SESSION_ID,
            'session_id': SESSION_ID,
            'domain': DOMAIN,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }
        self.validate_request(request, expected_request_data)

    def test_next(self):
        action = "next"
        with MockFormplayerRequest(action, QUESTION_RESPONSE) as mocker:
            self.interface.next()

        mocker.assert_exactly_one_request()
        request = mocker.get_last_request()

        expected_request_data = {
            'action': action,
            'session-id': SESSION_ID,
            'session_id': SESSION_ID,
            'domain': DOMAIN,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }
        self.validate_request(request, expected_request_data)

    def validate_request(self, request, expected_request_data):
        self.assertEqual(request.json(), expected_request_data)
        headers = request.headers
        self.assertEqual(headers["X-FORMPLAYER-SESSION"], USER_ID)
        self.assertNotEqual(headers["X-MAC-DIGEST"], "")


class MockFormplayerRequest:
    def __init__(self, action, mock_response):
        self.action = action
        self.mock_response = mock_response
        self.mocker = requests_mock.Mocker()

    def __enter__(self):
        self.mocker.__enter__()
        self.mocker.post(f"{get_formplayer_url()}/{self.action}", json=self.mock_response)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mocker.__exit__(exc_type, exc_val, exc_tb)

    def assert_exactly_one_request(self):
        assert len(self.mocker.request_history) == 1

    def get_last_request(self):
        return self.mocker.request_history[-1]
