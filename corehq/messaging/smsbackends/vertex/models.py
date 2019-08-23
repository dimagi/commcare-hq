# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
import requests

from dimagi.utils.logging import notify_exception
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.const import (
    TEXT_MSG_TYPE,
    UNICODE_MSG_TYPE,
    VERTEX_URL,
    SUCCESS_RESPONSE_REGEX_MATCHER,
    GATEWAY_ERROR_MESSAGE_REGEX_MATCHER,
    INCORRECT_MOBILE_NUMBER_CODE,
    GATEWAY_ERROR_CODES,
    GATEWAY_ERROR_MESSAGES,
)
from corehq.messaging.smsbackends.vertex.exceptions import VertexBackendException
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import strip_plus
from django.conf import settings


class VertexBackend(SQLSMSBackend):
    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'VERTEX'

    @classmethod
    def get_generic_name(cls):
        return "Vertex"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'password',
            'senderid',
        ]

    @classmethod
    def get_form_class(cls):
        return VertexBackendForm

    def populate_params(self, msg_obj):
        config = self.config
        try:
            message = msg_obj.text.encode('ascii')
            msgtype = TEXT_MSG_TYPE
        except UnicodeEncodeError:
            message = msg_obj.text.encode('utf-8')
            msgtype = UNICODE_MSG_TYPE
        params = {
            'username': config.username,
            'pass': config.password,
            'senderid': config.senderid,
            'response': 'Y',
            # It must include the country code appended before the mobile number
            # The mobile number should contain only numbers and no symbols like "+", "-" etc.
            'dest_mobileno': strip_plus(msg_obj.phone_number),
            'msgtype': msgtype,  # TXT/UNI/FLASH/WAP,
            'message': message
        }
        return params

    def phone_number_is_valid(self, phone_number):
        phone_number = strip_plus(phone_number)
        # Phone number must be an Indian phone number
        # Also avoid processing numbers that are obviously too short
        return phone_number.startswith('91') and len(phone_number) > 3

    def send(self, msg_obj, *args, **kwargs):
        if not self.phone_number_is_valid(msg_obj.phone_number):
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        params = self.populate_params(msg_obj)
        resp = requests.get(VERTEX_URL, params=params, timeout=settings.SMS_GATEWAY_TIMEOUT)
        self.handle_response(msg_obj, resp.status_code, resp.text)

    def handle_response(self, msg_obj, resp_status_code, resp_text):
        # in case of success store the complete response msg which should be like
        # 570737298-2017_05_27 AS-IS. This complete id referred to as "Scheduleid"
        # can be then used to enquire for status of this particular SMS
        if SUCCESS_RESPONSE_REGEX_MATCHER.match(resp_text):
            msg_obj.backend_message_id = resp_text
        else:
            self.handle_failure(msg_obj, resp_status_code, resp_text)

    def handle_failure(self, msg_obj, resp_status_code, error_message):
        error_code, text = GATEWAY_ERROR_MESSAGE_REGEX_MATCHER.match(error_message).groups()
        if error_code and error_code == INCORRECT_MOBILE_NUMBER_CODE:
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
        elif (
            error_code in GATEWAY_ERROR_CODES or
            error_message in GATEWAY_ERROR_MESSAGES
        ):
            msg_obj.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
            notify_error_message = "Error with the Vertex SMS Backend: " + error_message
            notify_exception(None, notify_error_message)
        else:
            raise VertexBackendException(
                "Unrecognized response from Vertex gateway with {response_status_code} "
                "status code, response {response_text}".format(
                    response_status_code=resp_status_code,
                    response_text=error_message)
            )
