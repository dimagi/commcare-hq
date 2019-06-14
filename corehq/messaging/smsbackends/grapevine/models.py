from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree
from django.http import HttpResponse
from tastypie.authentication import Authentication
from tastypie.authorization import Authorization
from tastypie.resources import Resource
from tastypie.serializers import Serializer
from tastypie.throttle import CacheThrottle
from corehq.messaging.smsbackends.grapevine.forms import GrapevineBackendForm
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SQLSMSBackend
from xml.sax.saxutils import escape, unescape
from django.conf import settings
from corehq.apps.sms.api import incoming as incoming_sms
import logging
import requests
import six

logger = logging.getLogger(__name__)

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
    <gviSmsMessage>
        <affiliateCode>{affiliate_code}</affiliateCode>
        <authenticationCode>{auth_code}</authenticationCode>
        <messageType>text</messageType>
        <recipientList>
            <message>{message}</message>
            <recipient>
                <msisdn>{msisdn}</msisdn>
            </recipient>
        </recipientList>
    </gviSmsMessage>"""


class GrapevineException(Exception):
    pass


class SQLGrapevineBackend(SQLSMSBackend):

    show_inbound_api_key_during_edit = False

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'affiliate_code',
            'authentication_code',
        ]

    @classmethod
    def get_opt_in_keywords(cls):
        return ['START']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP', 'END', 'CANCEL', 'UNSUBSCRIBE', 'QUIT']

    @classmethod
    def get_api_id(cls):
        return 'GVI'

    @classmethod
    def get_generic_name(cls):
        return "Grapevine"

    @classmethod
    def get_form_class(cls):
        return GrapevineBackendForm

    def handle_response(self, response):
        """
        Raising an exception makes the framework retry sending the message.
        """
        status_code = response.status_code
        response_text = response.text

        if status_code != 200:
            raise GrapevineException("Received status code %s" % status_code)

        try:
            root = ElementTree.fromstring(response_text)
        except (TypeError, ElementTree.ParseError):
            raise GrapevineException("Invalid XML returned from API")

        result_code = root.find('resultCode')
        if result_code is None:
            raise GrapevineException("resultCode tag not found in XML response")

        if result_code.text != '0':
            raise GrapevineException("Received non-zero result code: %s" % result_code.text)

    def send(self, msg, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        text = msg.text

        config = self.config
        data = TEMPLATE.format(
            affiliate_code=escape(config.affiliate_code),
            auth_code=escape(config.authentication_code),
            message=escape(text),
            msisdn=escape(phone_number)
        )

        url = 'http://www.gvi.bms9.vine.co.za/httpInputhandler/ApplinkUpload'

        response = requests.post(
            url,
            data=data.encode('utf-8'),
            headers={'content-type': 'text/xml'},
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        self.handle_response(response)


class SmsMessage(object):
    phonenumber = ''
    text = ''

    def __init__(self, phonenumber=None, text=None):
        self.phonenumber = phonenumber
        self.text = unescape(text) if text else ''

    @property
    def is_complete(self):
        return bool(self.phonenumber)


class UrlencodedDeserializer(Serializer):
    formats = ['json', 'jsonp', 'xml', 'yaml', 'html', 'plist', 'urlencode']
    content_types = {
        'json': 'application/json',
        'jsonp': 'text/javascript',
        'xml': 'application/xml',
        'yaml': 'text/yaml',
        'html': 'text/html',
        'plist': 'application/x-plist',
        'urlencode': 'application/x-www-form-urlencoded',
    }

    def from_urlencode(self, data, options=None):
        """ handles basic form encoded url posts """
        qs = dict((k, v if len(v) > 1 else v[0])
            for k, v in six.iteritems(six.moves.urllib.parse.parse_qs(data)))

        return qs

    def to_urlencode(self, content):
        pass


class SimpleApiAuthentication(Authentication):

    def is_authenticated(self, request, **kwargs):
        user = self.get_identifier(request)
        key = request.GET.get('apikey')

        expected_key = getattr(settings, 'SIMPLE_API_KEYS', {}).get(user)
        if not expected_key:
            logger.warning("No apikey defined for user '%s'" % user)
        return expected_key and key == expected_key

    def get_identifier(self, request):
        return request.GET.get('apiuser', 'nouser')


class GrapevineResource(Resource):
    """
    Handles grapevine messaging requests

    * incoming SMS
        <gviSms>
            <smsDateTime>2013-10-29T12:55:58</smsDateTime>
            <gatewayIdentifier>vodacomPremMGA2Rx1</gatewayIdentifier>
            <cellNumber>27827891099</cellNumber>
            <smsLocation>30665</smsLocation>
            <content>Another test</content>
        </gviSms>

    * Replies to SMS
        <gviSmsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <responseDateTime>2013-10-29T13:19:07</responseDateTime>
            <recipient>
                <msisdn>27827891099</msisdn>
            </recipient>
            <responseType>reply</responseType>
            <response>Test reply</response>
        </gviSmsResponse>

    * SMS Status reports (not currently implemented)
        <gviSmsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <responseDateTime>2013-10-29T13:15:52</responseDateTime>
            <submitDateTime>2013-10-29T13:15:49</submitDateTime>
            <recipient>
                <msisdn>27827891099</msisdn>
            </recipient>
            <responseType>receipt</responseType>
            <status>
                <code>0</code>
                <reason>Message is delivered to destination. stat:DELIVRD</reason>
            </status>
        </gviSmsResponse>

    smsDateTime: The date and time when the original SMS arrived at GVI's SMS gateway.
    gatewayIdentifier: Identifies the network and the rate of the SMS.
    cellNumber: The number (in international MSISDN format) of the mobile phone that sent the SMS.
    smsLocation: The short code to which the SMS was sent.
    content: The message text of the SMS message.
    """
    class Meta(object):
        resource_name = 'sms'
        object_class = SmsMessage
        authorization = Authorization()
        allowed_methods = ['post']
        serializer = UrlencodedDeserializer()
        throttle = CacheThrottle(throttle_at=600, timeframe=60, expiration=86400)
        authentication = SimpleApiAuthentication()

    def detail_uri_kwargs(self, bundle_or_obj):
        return {}

    def full_hydrate(self, bundle):
        if not bundle.data or not bundle.data.get('XML'):
            return bundle

        # http://bugs.python.org/issue11033
        xml = bundle.data['XML'].encode('utf-8')

        root = ElementTree.fromstring(xml)
        if root.tag == 'gviSms':
            date_string = root.find('smsDateTime').text
            phone_number = root.find('cellNumber').text
            content_text = root.find('content').text
            if six.PY2:
                phone_number = phone_number.decode('utf-8')
                content_text = content_text.decode('utf-8')
            bundle.obj = SmsMessage(phone_number, content_text)

        elif root.tag == 'gviSmsResponse':
            date_string = root.find('responseDateTime').text
            phone_number = root.find('recipient/msisdn').text
            resp_type = root.find('responseType').text  # receipt, reply or error

            if resp_type == 'reply':
                response_text = root.find('response').text
                if six.PY2:
                    phone_number = phone_number.decode('utf-8')
                    response_text = response_text.decode('utf-8')
                bundle.obj = SmsMessage(phone_number, response_text)

        return bundle

    def obj_create(self, bundle, request=None, **kwargs):
        bundle = self.full_hydrate(bundle)

        if bundle.obj.is_complete:
            incoming_sms(bundle.obj.phonenumber, bundle.obj.text, SQLGrapevineBackend.get_api_id())

        return bundle

    def post_list(self, request, **kwargs):
        super(GrapevineResource, self).post_list(request, **kwargs)
        # respond with 200 OK instead of 201 CREATED
        return HttpResponse()

