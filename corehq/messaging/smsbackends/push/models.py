import requests
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.push.forms import PushBackendForm
from django.conf import settings
from lxml import etree
from xml.sax.saxutils import escape


OUTBOUND_REQUEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
    <methodName>EAPIGateway.SendSMS</methodName>
    <params>
        <param>
            <value>
                <struct>
                    <member>
                        <name>Password</name>
                        <value>{password}</value>
                    </member>
                    <member>
                        <name>Channel</name>
                        <value><int>{channel}</int></value>
                    </member>
                    <member>
                        <name>Service</name>
                        <value><int>{service}</int></value>
                    </member>
                    <member>
                        <name>SMSText</name>
                        <value>{text}</value>
                    </member>
                    <member>
                        <name>Numbers</name>
                        <value>{number}</value>
                    </member>
                </struct>
            </value>
        </param>
    </params>
</methodCall>
"""


class PushException(Exception):
    pass


class PushBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'channel',
            'service',
            'password',
        ]

    @classmethod
    def get_url(cls):
        return 'http://41.77.230.124:9080'

    @classmethod
    def get_api_id(cls):
        return 'PUSH'

    @classmethod
    def get_generic_name(cls):
        return "Push"

    @classmethod
    def get_form_class(cls):
        return PushBackendForm

    def response_is_error(self, response):
        return response.status_code != 200

    def handle_error(self, response, msg):
        raise PushException("Received HTTP response %s from push backend" % response.status_code)

    def handle_success(self, response, msg):
        response.encoding = 'utf-8'
        if not response.text:
            return

        try:
            xml = etree.fromstring(response.text.encode('utf-8'))
        except etree.XMLSyntaxError:
            return

        data_points = xml.xpath('/methodResponse/params/param/value/struct/member')
        for data_point in data_points:
            name = data_point.xpath('name/text()')
            name = name[0] if name else None

            if name == 'Identifier':
                value = data_point.xpath('value/string/text()')
                value = value[0] if value else None
                msg.backend_message_id = value
                break

    def get_outbound_payload(self, msg):
        config = self.config
        return OUTBOUND_REQUEST_XML.format(
            channel=escape(config.channel),
            service=escape(config.service),
            password=escape(config.password),
            number=escape(msg.phone_number),
            text=escape(msg.text.encode('utf-8')),
        )

    def send(self, msg, *args, **kwargs):
        headers = {'Content-Type': 'application/xml'}
        payload = self.get_outbound_payload(msg)
        response = requests.post(
            self.get_url(),
            data=payload,
            headers=headers,
            timeout=settings.SMS_GATEWAY_TIMEOUT
        )

        if self.response_is_error(response):
            self.handle_error(response, msg)
        else:
            self.handle_success(response, msg)
