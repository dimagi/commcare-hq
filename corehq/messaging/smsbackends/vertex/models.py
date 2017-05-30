# -*- coding: utf-8 -*-
import requests

from corehq.messaging.smsbackends.http.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.const import (
    TEXT_MSG_TYPE,
    UNICODE_MSG_TYPE,
    VERTEX_URL,
    SUCCESS_RESPONSE_REGEX_MATCHER,
)
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm
from corehq.apps.sms.util import strip_plus


class VertexBackend(SQLSMSBackend):
    class Meta:
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
            message = str(msg_obj.text)
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

    def send(self, msg_obj, *args, **kwargs):
        params = self.populate_params(msg_obj)
        resp = requests.get(VERTEX_URL, params=params)
        self.handle_response(msg_obj, resp.text)

    def handle_response(self, msg_obj, resp):
        # in case of success store the complete response msg which should be like
        # 570737298-2017_05_27 AS-IS. This complete id referred to as "Scheduleid"
        # can be then used to enquire for status of this particular SMS
        if SUCCESS_RESPONSE_REGEX_MATCHER.match(resp):
            msg_obj.backend_message_id = resp
        else:
            msg_obj.set_system_error(resp)
