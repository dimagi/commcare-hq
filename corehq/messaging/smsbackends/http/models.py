import sys

from django.conf import settings

import six
from urllib.parse import urlencode
from urllib.request import urlopen

from corehq.apps.sms.mixin import BackendProcessingException
from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number, strip_plus
from corehq.messaging.smsbackends.http.sms_sending import verify_sms_url

from .forms import HttpBackendForm


class SQLHttpBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            # the url to send to
            'url',
            # the parameter which the gateway expects to represent the sms message
            'message_param',
            # the parameter which the gateway expects to represent the phone number to send to
            'number_param',
            # True to include the plus sign in front of the number, False not to (optional, defaults to False)
            'include_plus',
            # "GET" or "POST" (optional, defaults to "GET")
            'method',
            # a dictionary of additional parameters that will be sent in the request (optional)
            'additional_params',
        ]

    @classmethod
    def get_api_id(cls):
        return 'HTTP'

    @classmethod
    def get_generic_name(cls):
        return "HTTP"

    @classmethod
    def get_form_class(cls):
        return HttpBackendForm

    @property
    def url(self):
        return self.config.url

    @property
    def extra_urlopen_kwargs(self):
        return {}

    def send(self, msg, *args, **kwargs):
        config = self.config
        if config.additional_params:
            params = config.additional_params.copy()
        else:
            params = {}

        phone_number = msg.phone_number
        if config.include_plus:
            phone_number = clean_phone_number(phone_number)
        else:
            phone_number = strip_plus(phone_number)

        params[config.message_param] = self._encode_http_message(msg.text)
        params[config.number_param] = phone_number

        verify_sms_url(config.url, msg, backend=self)

        url_params = urlencode(params)
        try:
            if config.method == "GET":
                urlopen(
                    "%s?%s" % (config.url, url_params),
                    timeout=settings.SMS_GATEWAY_TIMEOUT,
                    **self.extra_urlopen_kwargs,
                ).read()
            else:
                urlopen(
                    config.url,
                    url_params,
                    timeout=settings.SMS_GATEWAY_TIMEOUT,
                    **self.extra_urlopen_kwargs,
                ).read()
        except Exception as e:
            msg = "Error sending message from backend: '{}'\n\n{}".format(self.pk, str(e))
            six.reraise(BackendProcessingException, BackendProcessingException(msg), sys.exc_info()[2])

    @staticmethod
    def _encode_http_message(text):
        try:
            return text.encode("iso-8859-1")
        except UnicodeEncodeError:
            return text.encode("utf-8")
