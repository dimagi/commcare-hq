from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.mixin import SMSBackend
from couchdbkit.ext.django.schema import *

class HttpBackend(SMSBackend):
    url                 = StringProperty() # the url to send to
    message_param       = StringProperty() # the parameter which the gateway expects to represent the sms message
    number_param        = StringProperty() # the parameter which the gateway expects to represent the phone number to send to
    include_plus        = BooleanProperty(default=False) # True to include the plus sign in front of the number, False not to (optional, defaults to False)
    method              = StringProperty(choices=["GET","POST"], default="GET") # "GET" or "POST" (optional, defaults to "GET")
    additional_params   = DictProperty() # a dictionary of additional parameters that will be sent in the request (optional)

    @classmethod
    def get_api_id(cls):
        return "HTTP"

    def send(msg, *args, **kwargs):
        """
        Expected kwargs:
            additional_params   a dictionary of additional parameters that will be sent in the request (optional, defaults to {})
        """
        if self.additional_params is not None:
            params = self.additional_params.copy()
        else:
            params = {}
        #
        phone_number = msg.phone_number
        if self.include_plus:
            if phone_number[0] != "+":
                phone_number = "+%s" % phone_number
        else:
            if phone_number[0] == "+":
                phone_number = phone_number[1:]
        #
        try:
            text = msg.text.encode("iso-8859-1")
        except UnicodeEncodeError:
            text = msg.text.encode("utf-8")
        params[self.message_param] = text
        params[self.number_param] = phone_number
        #
        url_params = urlencode(params)
        if self.method == "GET":
            response = urlopen("%s?%s" % (self.url, url_params)).read()
        else:
            response = urlopen(self.url, url_params).read()

