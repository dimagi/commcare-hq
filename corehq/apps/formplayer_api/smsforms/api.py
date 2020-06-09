"""
A set of wrappers that return the JSON bodies you use to interact with the formplayer
backend for various sets of tasks.

This API is currently highly beta and could use some hardening.
"""
import json
import socket

from django.conf import settings
from django.http import Http404

import requests
from requests import HTTPError
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest
from dimagi.utils.logging import notify_exception, notify_error


class TouchformsError(ValueError):

    def __init__(self, *args, **kwargs):
        self.response_data = kwargs.pop('response_data', {})
        super().__init__(*args, **kwargs)


class InvalidSessionIdException(TouchformsError):
    pass


class XFormsConfig(object):

    def __init__(self, form_content, language="", session_data=None,
                 domain=None, restore_as=None, restore_as_case_id=None):

        self.form_content = form_content
        self.language = language
        self.session_data = session_data
        self.restore_as = restore_as
        self.restore_as_case_id = restore_as_case_id
        self.domain = domain

    def start_session(self):
        """
        Start a new session based on this configuration
        """

        return _get_response(self._get_start_session_data(),
                             user_id=self.session_data.get('user_id'))

    def _get_start_session_data(self):
        """
        Translates this config into something formplayer wants to work with
        """

        ret = {
            "action": "new-form",
            "form-content": self.form_content,
            "session-data": self.session_data,
            "lang": self.language,
            'username': self.session_data.get('username'),
            'domain': self.session_data.get('domain'),
            'app_id': self.session_data.get('app_id'),
        }

        if self.restore_as_case_id:
            # The contact starting the survey is a case who will be
            # filling out the form for itself.
            ret['restoreAsCaseId'] = self.restore_as_case_id
        elif self.restore_as:
            # The contact starting the survey is a user.
            ret['restoreAs'] = self.restore_as
        else:
            raise ValueError("Unable to determine 'restore as' contact for formplayer")

        # only include anything with a value, or touchforms gets mad
        return {key: value for key, value in ret.items() if value}


class XformsEvent(object):
    """
    A wrapper for the json event object that comes back from touchforms, which
    looks approximately like this:n

    { "datatype":"select",
      "style":{},
      "choices":["red","green","blue"],
      "caption":"What's your favorite color?",
      "type":"question",
      "answer":null,
      "required":0,
      "ix":"1",
      "help":null
    }
    """
    def __init__(self, datadict):
        self._dict = datadict
        self.type = datadict["type"]
        self.caption = datadict.get("caption", "")
        self.datatype = datadict.get("datatype", "")
        self.output = datadict.get("output", "")
        self.choices = datadict.get("choices", None)

    @property
    def text_prompt(self):
        """
        A text-only prompt for this. Used in pure text (or sms) mode.

        Kept for backwards compatibility. Should use get_text_prompt, below.
        """
        return self.get_text_prompt()

    def get_text_prompt(self):
        """
        Get a text-only prompt for this. Used in pure text (or sms) mode.

        """
        if self.datatype == "select" or self.datatype == "multiselect":
            return select_to_text_compact(self.caption, self._dict["choices"])
        else:
            return self.caption


def select_to_text_compact(caption, choices):
    """
    A function to convert a select item to text in a compact format.
    Format is:

    [question] 1:[choice1], 2:[choice2]...
    """
    return "{} {}.".format(
        caption, ", ".join(["{}:{}".format(i + 1, val) for i, val in enumerate(choices)]))


class XformsResponse(object):
    """
    A wrapper for the json that comes back from touchforms,
    which looks approximately like this:

    {"event":
        { "datatype":"select",
          "style":{},
          ... (see above)
         },
     "session_id": 'd0addaa40dbcefefc6a687472a4e65d2',
     "status":"accepted",
     "seq_id":1}

    Although errors come back more like this:
    {'status': 'validation-error',
     'seq_id': 2,
     'reason': 'some message about constraint',
     'type': 'constraint'}

    """

    def __init__(self, datadict):
        self._dict = datadict
        self.is_error = False
        self.error = None
        if "event" in datadict and datadict["event"] is not None:
            self.event = XformsEvent(datadict["event"])
            self.text_prompt = self.event.text_prompt
        else:
            self.event = None

        self.seq_id = datadict.get("seq_id", "")
        self.session_id = datadict.get("session_id", "")
        self.status = datadict.get("status", "")

        # custom logic to handle errors
        if self.status == "validation-error":
            assert self.event is None, "There should be no touchforms event for errors"
            self.is_error = True
            self.text_prompt = datadict.get("reason", "that is not a legal answer")

        # custom logic to handle http related errors
        elif self.status == "http-error":
            assert self.event is None, "There should be no touchforms event for errors"
            self.error = datadict.get("error")
            self.is_error = True
            self.status_code = datadict.get("status_code")
            self.args = datadict.get("args")
            self.url = datadict.get("url")
        elif self.event is None:
            raise TouchformsError(
                "unhandleable response: {}"
                .format(json.dumps(datadict), response_data=datadict))

    @classmethod
    def server_down(cls):
        # TODO: this should probably be configurable
        return XformsResponse({"status": "http-error",
                               "error": "No response from server. Please "
                                        "contact your administrator for help."})


def _get_response(data, user_id):
    try:
        response_json = _post_data(data, user_id)
    except socket.error:
        return XformsResponse.server_down()
    else:
        return XformsResponse(response_json)


def _post_data(data, user_id):
    if not data.get("domain"):
        raise ValueError("Expected domain")

    if not user_id:
        notify_exception(
            None,
            "Making smsforms request w/o user_id. Will result in non-sticky session.",
            details={
                'session-id': data.get('session-id'),
            }
        )

    data = _get_formplayer_session_data(data)
    data_bytes = json.dumps(data).encode('utf-8')
    response = requests.post(
        url="{}/{}".format(get_formplayer_url(), data["action"]),
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "content-length": str(len(data_bytes)),
            "X-MAC-DIGEST": get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data_bytes),
            "X-FORMPLAYER-SESSION": user_id,
        },
    )
    if response.status_code == 404:
        raise Http404(response.reason)
    if 500 <= response.status_code < 600:
        http_error_msg = '{} Server Error: {} for url: {}'.format(
            response.status_code, response.reason, response.url)
        notify_error(http_error_msg, details={'response': response, 'body': response.text})
        raise HTTPError(http_error_msg, response=response)
    return response.json()


def _get_formplayer_session_data(data):
    data['oneQuestionPerScreen'] = True
    data['nav_mode'] = 'prompt'
    if "session_id" in data:
        session_id = data["session_id"]
    elif "session-id" in data:
        session_id = data["session-id"]
    else:
        return data

    data["session_id"] = session_id
    data["session-id"] = session_id
    return data


class FormplayerInterface:
    def __init__(self, session_id, domain, user_id=Ellipsis):
        self.session_id = session_id
        self.domain = domain
        self._user_id = user_id

    @property
    def user_id(self):
        from corehq.apps.smsforms.models import SQLXFormsSession

        if self._user_id is Ellipsis:
            session = SQLXFormsSession.by_session_id(self.session_id)
            if session:
                self._user_id = session.user_id
            else:
                self._user_id = None

        return self._user_id

    def get_raw_instance(self):
        """
        Gets the raw xml instance of the current session regardless of the state that we're in
        (used for logging partially complete forms to couch when errors happen).
        """

        data = {
            "action": "get-instance",
            "session-id": self.session_id,
            "domain": self.domain
        }

        response = _post_data(data, self.user_id)
        if "error" in response:
            error = response["error"]
            if error == "Form session not found":
                raise InvalidSessionIdException("Invalid Session Id")
            else:
                raise TouchformsError(error)
        return response

    def answer_question(self, answer):
        """
        Answer a question.
        """
        data = {"action": "answer",
                "session-id": self.session_id,
                "answer": answer,
                "domain": self.domain}
        return _get_response(data, self.user_id)

    def current_question(self):
        """
        Retrieves information about the current question.
        """
        data = {"action": "current",
                "session-id": self.session_id,
                "domain": self.domain}
        return _get_response(data, self.user_id)

    def next(self):
        """
        Moves to the next question.
        """
        data = {"action": "next",
                "session-id": self.session_id,
                "domain": self.domain}
        return _get_response(data, self.user_id)
