from contextlib import contextmanager
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.util import get_cloudcare_session_data
from corehq.apps.cloudcare.touchforms_api import get_session_data
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.users.models import CouchUser
from touchforms.formplayer.api import XFormsConfig, DigestAuth, answer_question, next as next_question


class FormSession(object):

    def __init__(self, auth, response):
        self._auth = auth
        # self._response = response
        self.session_id = response.session_id

    def submit_answer(self, answer):
        # self._response
        response = answer_question(self.session_id, answer, self._auth)
        responses = [r for r in self.iter_response(response)]
        return responses

    def iter_response(self, response):
        # Modelled on touchforms.formplayer.sms._next_responses but not coupled to SMS
        if response.is_error:
            yield response
        elif response.event.type == "sub-group":
            resp = next_question(self.session_id, self._auth)
            for r in self.iter_response(resp):
                yield r
        elif response.event.type == "question":
            yield response
            if response.event.datatype == "info":
                # Send "ok" for label questions
                resp = answer_question(self.session_id, 'ok', self._auth)
                for r in self.iter_response(resp):
                    yield r
        elif response.event.type == "form-complete":
            yield response


class FormPlayerApiClient(object):
    def __init__(self, host, username, password):
        self._host = host
        self._username = username
        self._password = password

    @contextmanager
    def form_session(self, domain, username, app_id, module_id, xmlns):
        # See smsforms.app.start_session
        user = CouchUser.get_by_username(username)
        app = get_app(domain, app_id)
        form = app.get_form_by_xmlns(xmlns)
        session_data = get_session_data(domain, user, case_id=None, device_id=COMMCONNECT_DEVICE_ID)
        session_data["additional_filters"] = {
            "user_id": user.get_id,
            "footprint": "true"
        }
        session_data.update(get_cloudcare_session_data(domain, form, user))
        auth = DigestAuth(self._username, self._password)
        config = XFormsConfig(
            form_content=form.render_xform(),
            language=user.get_language_code(),
            session_data=session_data,
            auth=auth)
        response = config.start_session()
        yield FormSession(auth, response)
