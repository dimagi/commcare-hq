from corehq.apps.formplayer_api.smsforms.api import FormplayerInterface
from corehq.apps.formplayer_api.smsforms.signals import sms_form_complete


class SessionStartInfo(object):
    session_id = None
    _first_response = None
    _first_responses = None

    def __init__(self, first_response, domain):
        self.session_id = first_response.session_id
        self._first_response = first_response
        self.domain = domain

    @property
    def first_responses(self):
        if self._first_responses is None:
            self._first_responses = list(_next_responses(
                self._first_response, FormplayerInterface(self.session_id, self.domain)))
        return self._first_responses


def start_session(config):
    """
    Starts a session in touchforms based on the config. Returns a
    SessionStartInfo object with session id and initial responses.
    """
    xformsresponse = config.start_session()
    return SessionStartInfo(xformsresponse, config.domain)


def next_responses(session_id, answer, domain):
    formplayer_interface = FormplayerInterface(session_id, domain)
    if answer:
        xformsresponse = formplayer_interface.answer_question(_tf_format(answer))
    else:
        xformsresponse = formplayer_interface.next()
    for resp in _next_responses(xformsresponse, formplayer_interface):
        yield resp


def _next_responses(xformsresponse, formplayer_interface):
    if xformsresponse.is_error:
        yield xformsresponse
    elif xformsresponse.event.type == "sub-group":
        response = formplayer_interface.next()
        for additional_resp in _next_responses(response, formplayer_interface):
            yield additional_resp
    elif xformsresponse.event.type == "question":
        yield xformsresponse
        if xformsresponse.event.datatype == "info":
            # We have to deal with Trigger/Label type messages 
            # expecting an 'ok' type response. So auto-send that 
            # and move on to the next question.
            response = formplayer_interface.answer_question('ok')
            for additional_resp in _next_responses(response, formplayer_interface):
                yield additional_resp
    elif xformsresponse.event.type == "form-complete":
        sms_form_complete.send(sender="touchforms", session_id=formplayer_interface.session_id,
                               form=xformsresponse.event.output)
        yield xformsresponse


def _tf_format(text):
    # any additional formatting needs can go here if they come up
    # be careful to check datatypes before casting i.e., ok to cast an
    # integer question to an int, but don't cast text questions to int
    # because it will strip leading zeroes.
    return text
