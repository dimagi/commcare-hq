from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.conf import settings
from django.http import Http404
from requests import HTTPError
from six.moves.urllib.parse import urlparse
import six.moves.http_client
import socket
import copy
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.form_processor.utils.general import use_sqlite_backend
from corehq.util.hmac_request import get_hmac_digest, convert_to_bytestring_if_unicode
from corehq.apps.formplayer_api.smsforms.exceptions import BadDataError
from corehq.apps.formplayer_api.utils import get_formplayer_url
import requests
"""
A set of wrappers that return the JSON bodies you use to interact with the formplayer
backend for various sets of tasks.

This API is currently highly beta and could use some hardening. 
"""


class TouchformsAuth(object):
    """
    Used to authenticate with touchforms
    """
    def __init__(self, type, key):
        self.type = type
        self.key = key
        
    def to_dict(self):
        return {'type': self.type, 'key': self.key}


class DjangoAuth(TouchformsAuth):
    
    def __init__(self, key):
        super(DjangoAuth, self).__init__("django-session", key)
            

class DigestAuth(TouchformsAuth):
    
    def __init__(self, username, password):
        self.username = username
        super(DigestAuth, self).__init__("http-digest", password)
        
    def to_dict(self):
        return {'type': self.type, 'key': self.key, 'username': self.username}


class TouchformsError(ValueError):

    def __init__(self, *args, **kwargs):
        self.response_data = kwargs.pop('response_data', {})
        super(TouchformsError, self).__init__(*args, **kwargs)


class InvalidSessionIdException(TouchformsError):
    pass


class XFormsConfigException(ValueError):
    pass


class XFormsConfig(object):
    
    def __init__(self, form_path=None, form_content=None, language="", 
                 session_data=None, preloader_data={}, instance_content=None,
                 touchforms_url=None, auth=None, domain=None, restore_as=None, restore_as_case_id=None):
        
        if bool(form_path) == bool(form_content):
            raise XFormsConfigException\
                ("Can specify file path or content but not both!\n" 
                 "File Path: %s, Form Content: %s" % (form_path, form_content))
        
        self.form_path = form_path
        self.form_content = form_content
        self.language = language
        self.session_data = session_data
        self.preloader_data = preloader_data        
        self.instance_content = instance_content
        self.auth = auth
        self.restore_as = restore_as
        self.restore_as_case_id = restore_as_case_id
        self.domain = domain
        
    def get_touchforms_dict(self):
        """
        Translates this config into something touchforms wants to 
        work with
        """
        
        vals = (("action", "new-form"),
                ("form-name", self.form_path),
                ("form-content", self.form_content),
                ("instance-content", self.instance_content),
                ("preloader-data", self.preloader_data),
                ("session-data", self.session_data),
                ("lang", self.language),
                ("form-url", self.form_path))
        
        # only include anything with a value, or touchforms gets mad
        ret = dict([x for x in vals if x[1]])
        self.add_key_helper('username', ret)
        self.add_key_helper('domain', ret)
        self.add_key_helper('app_id', ret)

        if self.restore_as_case_id:
            # The contact starting the survey is a case who will be
            # filling out the form for itself.
            ret['restoreAsCaseId'] = self.restore_as_case_id
        elif self.restore_as:
            # The contact starting the survey is a user.
            ret['restoreAs'] = self.restore_as
        else:
            raise ValueError("Unable to determine 'restore as' contact for formplayer")

        return ret

    def add_key_helper(self, key, ret):
        if key in self.session_data:
            ret[key] = self.session_data[key]
        
    def start_session(self):
        """
        Start a new session based on this configuration
        """

        return get_response(json.dumps(self.get_touchforms_dict()), auth=self.auth)
    

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
        return self.get_text_prompt(None)
    
    def get_text_prompt(self, select_display_func=None):
        """
        Get a text-only prompt for this. Used in pure text (or sms) mode.
        
        Allows you to pass in a function to override how selects are displayed.
        
        The signature of that function should take in the prompt and choice list
        and return a string. The default is select_to_text_compact
        """
        display_func = select_display_func or select_to_text_compact
        if self.datatype == "select" or self.datatype == "multiselect":
            return display_func(self.caption, self._dict["choices"])
        else:
            return self.caption


def select_to_text_compact(caption, choices):
    """
    A function to convert a select item to text in a compact format.
    Format is:
    
    [question] 1:[choice1], 2:[choice2]...
    """
    return "%s %s." % (caption,
                      ", ".join(["%s:%s" % (i+1, val) for i, val in \
                                 enumerate(choices)])) 


def select_to_text_vals_only(caption, choices):
    """
    A function to convert a select item to text in a compact format.
    Format is:
    
    [question], choices: [choice1], [choice2]...
    """
    return "%s, choices: %s" % (caption, ", ".join(choices)) 
                  

def select_to_text_readable(caption, choices):
    """
    A function to convert a select item to text in a more verbose, readable 
    format.
    Format is:
    
    [question] Send 1 for [choice1], 2 for [choice2]...
    """
    return "%s Send %s" % (caption,
                      ", ".join(["%s for %s" % (i+1, val) for i, val in \
                                 enumerate(choices)])) 


def select_to_text_caption_only(caption, choices):
    """
    A select choices => text function that ignores choice captions entirely.
    All presentation of choices must be included in the main question caption.
    A DRY violation, for sure, but gives the maximum flexibility
    """
    return caption


class XformsResponse(object):
    """
    A wrapper for the json that comes back from touchforms, which 
    looks approximately like this:
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
        
        self.seq_id = datadict.get("seq_id","")
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
            raise TouchformsError("unhandleable response: %s" % json.dumps(datadict),
                response_data=datadict)

    @classmethod
    def server_down(cls):
        # TODO: this should probably be configurable
        return XformsResponse({"status": "http-error",
                               "error": "No response from server. Please "
                                        "contact your administrator for help."})


def formplayer_post_data_helper(d, content_type, url):
    data = json.dumps(d).encode('utf-8')
    headers = {}
    headers["Content-Type"] = content_type
    headers["content-length"] = str(len(data))
    headers["X-MAC-DIGEST"] = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data)
    response = requests.post(
        url,
        data=data,
        headers=headers
    )
    if response.status_code == 404:
        raise Http404(response.reason)
    if 500 <= response.status_code < 600:
        http_error_msg = '%s Server Error: %s for url: %s' % (response.status_code, response.reason, response.url)
        raise HTTPError(http_error_msg, response=response)
    return response.json()


def post_data(data, auth=None, content_type="application/json"):
    try:
        d = json.loads(data)
    except TypeError:
        raise BadDataError('unhandleable touchforms query: %s' % data)

    domain = d.get("domain")

    if not domain:
        raise ValueError("Expected domain")

    d = get_formplayer_session_data(d)
    return formplayer_post_data_helper(d, content_type, get_formplayer_url() + "/" + d["action"])


def get_formplayer_session_data(data):
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


def get_response(data, auth=None):
    try:
        response_json = post_data(data, auth=auth)
    except socket.error as e:
        return XformsResponse.server_down()
    try:
        return XformsResponse(response_json)
    except Exception as e:
        raise e


def sync_db(username, domain, auth):
    data = {
        "action":"sync-db",
        "username": username,
        "domain": domain
    }

    return post_data(json.dumps(data), auth)


def get_raw_instance(session_id, domain=None, auth=None):
    """
    Gets the raw xml instance of the current session regardless of the state that we're in (used for logging partially complete
    forms to couch when errors happen).
    """

    data = {
        "action":"get-instance",
        "session-id": session_id,
        "domain": domain
    }

    response = post_data(json.dumps(data), auth)
    if "error" in response:
        error = response["error"]
        if error == "Form session not found":
            raise InvalidSessionIdException("Invalid Session Id")
        else:
            raise TouchformsError(error)
    return response


def start_form_session(form_path, content=None, language="", session_data={}):
    """
    Start a new form session
    """
    # TODO: this method has been deprecated and the config object
    # should just be used directly. Temporarily left to support legacy code.
    return XFormsConfig(form_path=form_path,
                        instance_content=content,
                        session_data=session_data,
                        language=language).start_session()


def answer_question(session_id, answer, domain, auth=None):
    """
    Answer a question. 
    """
    data = {"action": "answer",
            "session-id": session_id,
            "answer": answer,
            "domain": domain}
    return get_response(json.dumps(data), auth)


def current_question(session_id, domain, auth=None):
    """
    Retrieves information about the current question.
    """
    data = {"action": "current",
            "session-id": session_id,
            "domain": domain}
    return get_response(json.dumps(data), auth)


def next(session_id, domain, auth=None):
    """
    Moves to the next question.
    """
    data = {"action": "next",
            "session-id": session_id,
            "domain": domain}
    return get_response(json.dumps(data), auth)
