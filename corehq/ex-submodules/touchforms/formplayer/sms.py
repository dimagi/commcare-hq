from touchforms.formplayer.api import answer_question, next
from touchforms.formplayer.signals import sms_form_complete

class SessionStartInfo(object):
    session_id = None
    _first_response = None
    _first_responses = None

    def __init__(self, first_response):
        self.session_id = first_response.session_id
        self._first_response = first_response

    @property
    def first_responses(self):
        if self._first_responses is None:
            self._first_responses = list(_next_responses(self._first_response, self.session_id))
        return self._first_responses

def start_session(config):
    """
    Starts a session in touchforms based on the config. Returns a
    SessionStartInfo object with session id and initial responses.
    """
    xformsresponse = config.start_session()
    return SessionStartInfo(xformsresponse)

def next_responses(session_id, answer, auth=None):
    xformsresponse = answer_question(session_id, _tf_format(answer), auth)
    for resp in _next_responses(xformsresponse, session_id, auth):
        yield resp

def _next_responses(xformsresponse, session_id, auth=None):
    if xformsresponse.is_error:
        yield xformsresponse
    elif xformsresponse.event.type == "sub-group":
        response = next(session_id, auth)
        for additional_resp in _next_responses(response, session_id, auth):
            yield additional_resp
    elif xformsresponse.event.type == "question":
        yield xformsresponse
        if xformsresponse.event.datatype == "info":
            # We have to deal with Trigger/Label type messages 
            # expecting an 'ok' type response. So auto-send that 
            # and move on to the next question.
            response = answer_question(session_id, 'ok', auth)
            for additional_resp in _next_responses(response, session_id, auth):
                yield additional_resp
    elif xformsresponse.event.type == "form-complete":
        sms_form_complete.send(sender="touchforms", session_id=session_id,
                               form=xformsresponse.event.output)
        yield xformsresponse

def _tf_format(text):
    # any additional formatting needs can go here if they come up
    # be careful to check datatypes before casting i.e., ok to cast an
    # integer question to an int, but don't cast text questions to int
    # because it will strip leading zeroes.
    return text
