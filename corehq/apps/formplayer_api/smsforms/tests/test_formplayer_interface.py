import uuid

import requests_mock
from django.conf import settings
from django.test import TestCase

from corehq.apps.formplayer_api.smsforms.api import FormplayerInterface
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest


class TestFormplayerInterface(TestCase):
    def setUp(self):
        super().setUp()
        self.session_id = uuid.uuid4().hex
        self.domain = uuid.uuid4().hex
        self.user_id = uuid.uuid4().hex
        self.interface = FormplayerInterface(self.session_id, self.domain, self.user_id)

    def test_get_raw_instance(self):
        expected_request_data = {
            'action': 'get-instance',
            'session-id': self.session_id,
            'session_id': self.session_id,
            'domain': self.domain,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }
        self._test_request("get-instance", self.interface.get_raw_instance, expected_request_data, {})

    def test_answer_question(self):
        mock_response = {"event": {
            "datatype": "select",
            "choices": ["red", "green", "blue"],
            "caption": "What's your favorite color?",
            "type": "question",
            "answer": None,
            "required": 0,
            "ix": "1",
            "help": None
        }}

        expected_request_data = {
            'action': 'answer',
            'answer': 'answer1',
            'session-id': self.session_id,
            'session_id': self.session_id,
            'domain': self.domain,
            'oneQuestionPerScreen': True,
            'nav_mode': 'prompt',
        }

        def request_callable():
            self.interface.answer_question("answer1")

        self._test_request("answer", request_callable, expected_request_data, mock_response)

    def _test_request(self, action, request_callable, expected_request_data, mock_response):
        with requests_mock.Mocker() as m:
            m.post(f"{get_formplayer_url()}/{action}", json=mock_response)
            request_callable()
            request = m.request_history[0]
            self.assertEqual(request.json(), expected_request_data)
            headers = request.headers
            self.assertEqual(headers["X-FORMPLAYER-SESSION"], self.user_id)
            digest = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, request.text)
            self.assertEqual(headers["X-MAC-DIGEST"], digest)
