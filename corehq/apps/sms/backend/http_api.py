import re
from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.forms import BackendForm
from corehq.apps.reminders.forms import RecordListField
from django.forms.fields import *
from django.core.exceptions import ValidationError
from couchdbkit.ext.django.schema import *
from dimagi.utils.django.fields import TrimmedCharField
from corehq.apps.sms.util import clean_phone_number, strip_plus
from django.utils.translation import ugettext as _, ugettext_noop

BANNED_URL_REGEX = (
    r".*://.*commcarehq.org.*",
    r".*://10.*",
    r".*://172.16.*",
    r".*://192.168.*",
    r".*://127.0.0.1.*",
    r".*://.*localhost.*",
)

class HttpBackendForm(BackendForm):
    url = TrimmedCharField()
    message_param = TrimmedCharField()
    number_param = TrimmedCharField()
    include_plus = BooleanField(required=False)
    method = ChoiceField(choices=(("GET","GET"),("POST","POST")))
    additional_params = RecordListField(input_name="additional_params")

    def __init__(self, *args, **kwargs):
        if "initial" in kwargs and "additional_params" in kwargs["initial"]:
            additional_params_dict = kwargs["initial"]["additional_params"]
            kwargs["initial"]["additional_params"] = [{"name" : key, "value" : value} for key, value in additional_params_dict.items()]
        super(HttpBackendForm, self).__init__(*args, **kwargs)

    def clean_url(self):
        value = self.cleaned_data.get("url")
        for regex in BANNED_URL_REGEX:
            if re.match(regex, value):
                raise ValidationError(_("Invalid URL."))
        return value

    def clean_additional_params(self):
        value = self.cleaned_data.get("additional_params")
        result = {}
        for pair in value:
            name = pair["name"].strip()
            value = pair["value"].strip()
            if name == "" or value == "":
                raise ValidationError("Please enter both name and value.")
            if name in result:
                raise ValidationError("Parameter name entered twice: %s" % name)
            result[name] = value
        return result

class HttpBackend(SMSBackend):
    url = StringProperty() # the url to send to
    message_param = StringProperty() # the parameter which the gateway expects to represent the sms message
    number_param = StringProperty() # the parameter which the gateway expects to represent the phone number to send to
    include_plus = BooleanProperty(default=False) # True to include the plus sign in front of the number, False not to (optional, defaults to False)
    method = StringProperty(choices=["GET","POST"], default="GET") # "GET" or "POST" (optional, defaults to "GET")
    additional_params = DictProperty() # a dictionary of additional parameters that will be sent in the request (optional)

    @classmethod
    def get_api_id(cls):
        return "HTTP"

    @classmethod
    def get_generic_name(cls):
        return "HTTP"

    @classmethod
    def get_template(cls):
        return "sms/http_backend.html"

    @classmethod
    def get_form_class(cls):
        return HttpBackendForm

    def send(self, msg, *args, **kwargs):
        if self.additional_params is not None:
            params = self.additional_params.copy()
        else:
            params = {}
        
        phone_number = msg.phone_number
        if self.include_plus:
            phone_number = clean_phone_number(phone_number)
        else:
            phone_number = strip_plus(phone_number)
        
        try:
            text = msg.text.encode("iso-8859-1")
        except UnicodeEncodeError:
            text = msg.text.encode("utf-8")
        params[self.message_param] = text
        params[self.number_param] = phone_number
        
        url_params = urlencode(params)
        if self.method == "GET":
            response = urlopen("%s?%s" % (self.url, url_params)).read()
        else:
            response = urlopen(self.url, url_params).read()

