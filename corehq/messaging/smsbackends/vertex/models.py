import requests
import re

from corehq.messaging.smsbackends.http.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm
from corehq.apps.sms.util import strip_plus

VERTEX_URL = "http://www.smsjust.com/sms/user/urlsms.php"
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

    def send(self, msg, *args, **kwargs):
        config = self.config
        params = {
            'username': config.username,
            'pass': config.password,
            'senderid': config.senderid,
            'response': 'Y',
            # It must include the country code appended before the mobile number
            # The mobile number should contain only numbers and no symbols like "+", "-" etc.
            'dest_mobileno': strip_plus(msg.phone_number),
            'msgtype': 'UNI'  # TXT/UNI/FLASH/WAP
        }
        params['message'] = msg.text.encode('utf-8')
        resp = requests.get(VERTEX_URL, params=params)
        self.handle_response(msg, resp)
        return resp

    def handle_response(self, msg, resp):
        # in case of success store the complete response msg which should be like
        # 570737298-2017_05_27 AS-IS. This complete id referred to as "Scheduleid"
        # can be then used to enquire for status of this particular SMS
        if SUCCESS_RESPONSE_REGEX_MATCHER.match(resp):
            msg.backend_message_id = resp
        else:
            msg.set_system_error(resp)
