# -*- coding: utf-8 -*-
import requests
import re

from corehq.messaging.smsbackends.http.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm
from corehq.apps.sms.util import strip_plus

VERTEX_URL = "https://www.smsjust.com/sms/user/urlsms.php"
SUCCESS_RESPONSE_REGEX = r'^(\d+)-(20\d{2})_(\d{2})_(\d{2})$'  # 570737298-2017_05_27
SUCCESS_RESPONSE_REGEX_MATCHER = re.compile(SUCCESS_RESPONSE_REGEX)


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
        params = {
            'username': config.username,
            'pass': config.password,
            'senderid': config.senderid,
            'response': 'Y',
            # It must include the country code appended before the mobile number
            # The mobile number should contain only numbers and no symbols like "+", "-" etc.
            'dest_mobileno': strip_plus(msg_obj.phone_number),
            'msgtype': 'UNI'  # TXT/UNI/FLASH/WAP
        }
        params['message'] = msg_obj.text.encode('utf-8')
        return params

    def send(self, msg_obj, *args, **kwargs):
        params = self.populate_params(msg_obj)
        resp = requests.get(VERTEX_URL, params=params)
        self.handle_response(msg_obj, resp.content)
        return resp

    def handle_response(self, msg_obj, resp):
        # in case of success store the complete response msg which should be like
        # 570737298-2017_05_27 AS-IS. This complete id referred to as "Scheduleid"
        # can be then used to enquire for status of this particular SMS
        if SUCCESS_RESPONSE_REGEX_MATCHER.match(resp):
            msg_obj.backend_message_id = resp
            msg_obj.save()
        else:
            msg_obj.set_system_error(resp)
