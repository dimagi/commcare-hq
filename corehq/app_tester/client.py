from corehq.apps.cloudcare.touchforms_api import get_session_data
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID


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

    def open_form_session(self, domain, username, xmlns, lang='en'):
        # See smsforms.app.start_session, cloudcare.touchforms_api.get_session_data

        # TODO: user = CouchUser.get(domain, username)
        session_data = get_session_data(domain, user, case_id=None, device_id=COMMCONNECT_DEVICE_ID)

        config = XFormsConfig(
            form_path=form_path,
            instance_content=content,
            session_data=session_data,
            language=lang)
        response = config.start_session()


        return FormSession(response)
