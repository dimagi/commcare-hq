from contextlib import contextmanager

from corehq.apps.cloudcare.touchforms_api import get_session_data
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.users.models import CouchUser
from touchforms.formplayer.api import XFormsConfig


class FormSession(object):

    def __init__(self, session):
        self._session = session

    def iter_questions(self):
        # See formplayer.sms._next_responses to see what I'm trying to simplify here
        yield self._session.first_question  # This will need to become a method
        for question in self._session.next:  # And this
            yield question

    def submit_answer(self, question, answer):
        # See touchforms.formplayer.api.answer_question,
        pass


class FormPlayerApiClient(object):
    def __init__(self, host, username, password):
        self._host = host
        self._username = username
        self._password = password

    @contextmanager
    def form_session(self, domain, username, xmlns):
        user = CouchUser.get_by_username(username)
        session_data = get_session_data(domain, user, case_id=None, device_id=COMMCONNECT_DEVICE_ID)
        session_data["additional_filters"] = {
            "user_id": user.get_id,
            "footprint": "true"
        }
        Form.get_by_xmlns()

        # See smsforms.app.start_session, cloudcare.touchforms_api.get_session_data


        config = XFormsConfig(
            form_path=form_path,
            instance_content=content,
            session_data=session_data)
        response = config.start_session()
        yield FormSession(response)
