from __future__ import absolute_import
from __future__ import unicode_literals
import json
import requests
from corehq.apps.sms.models import SMS, SQLSMSBackend
from corehq.apps.sms.util import strip_plus
from corehq.messaging.smsbackends.apposit.forms import AppositBackendForm
from django.conf import settings


ETHIOPIA_COUNTRY_CODE = '251'


class AppositException(Exception):
    pass


class SQLAppositBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_opt_in_keywords(cls):
        return ['START']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP']

    @classmethod
    def get_available_extra_fields(cls):
        return [
            # the username used in basic auth on http requests
            'application_id',
            # the password used in basic auth on http requests
            'application_token',
            'from_number',
            'host',
        ]

    @property
    def url(self):
        return 'https://%s/mmp/api/v2/json/sms/send' % self.config.host

    @classmethod
    def get_api_id(cls):
        return 'APPOSIT'

    @classmethod
    def get_generic_name(cls):
        return 'Apposit'

    @classmethod
    def get_form_class(cls):
        return AppositBackendForm

    def response_is_error(self, response_json):
        return response_json.get('statusCode') not in ('0', 0)

    def is_ethiopia_number(self, msg):
        phone = strip_plus(msg.phone_number)
        return phone.startswith(ETHIOPIA_COUNTRY_CODE)

    def handle_error(self, response, response_json, msg):
        exception_message = "Error with the Apposit backend. Http response code: %s; Apposit status: %s %s"
        exception_params = (
            response.status_code,
            response_json.get('statusCode'),
            response_json.get('statusMessage'),
        )
        raise AppositException(exception_message % exception_params)

    def handle_success(self, response, response_json, msg):
        msg.backend_message_id = response_json.get('messageId')

    def send(self, msg, *args, **kwargs):
        if not self.is_ethiopia_number(msg):
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        config = self.config
        data = {
            'from': config.from_number,
            'to': msg.phone_number,
            'message': msg.text,
        }
        json_payload = json.dumps(data)
        response = requests.post(
            self.url,
            auth=(config.application_id, config.application_token),
            data=json_payload,
            headers={'content-type': 'application/json'},
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        try:
            response_json = response.json()
        except:
            raise AppositException("Could not parse json response. HTTP response code: %s" % response.status_code)

        if self.response_is_error(response_json):
            self.handle_error(response, response_json, msg)
        else:
            self.handle_success(response, response_json, msg)
