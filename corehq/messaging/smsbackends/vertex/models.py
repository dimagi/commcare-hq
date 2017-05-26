import urllib2, urllib
import re
from django.conf import settings
from corehq.messaging.smsbackends.http.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm

VERTEX_URL = "http://www.smsjust.com/sms/user/urlsms.php"
SUCCESS_RESPONSE_REGEX = r'^([0-9]+)-(20[0-9]{2})_([0-9]{2})_([0-9]{2})$'  # 570737298-2017_05_27
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
    def get_available_extra_fields(self):
        return [
            'username',
            'password',
            'senderid',
            'response',
        ]

    @classmethod
    def get_form_class(self):
        return VertexBackendForm

    def sanitize_message(self, message):
        return (message
                .replace('&', 'amp;')
                .replace('#', ';hash')
                .replace('+', 'plus;')
                .replace(',', 'comma;')
                )

    def send(self, msg, *args, **kwargs):
        config = self.config
        params = {
            'username': config.username,
            'pass': config.password,
            'senderid': config.senderid,
            'response': config.response,
            # It must include the country code appended before the mobile number
            # The mobile number should contain only numbers and no symbols like "+", "-" etc.
            'dest_mobileno': msg.phone_number,
            'msgtype': 'TXT'  # TXT/UNI/FLASH/WAP
        }
        message = self.sanitize_message(msg)
        params['message'] = message
        url = '%s?%s' % (VERTEX_URL, urllib.urlencode(params))
        resp = urllib2.urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()
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
