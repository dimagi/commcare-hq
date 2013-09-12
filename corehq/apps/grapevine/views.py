from corehq.apps.grapevine.api import GrapevineBackend
from corehq.apps.sms.api import incoming as incoming_sms
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.sax.saxutils import unescape

@csrf_exempt
def sms_in(request):
    """
    Handles grapevine messaging requests

    <gviSms>
        <smsDateTime>2005-09-08T10:06:03</smsDateTime>
        <gatewayIdentifier>ThreeRandVodaRx1</gatewayIdentifier>
        <cellNumber>27827891099</cellNumber>
        <smsLocation>35444</smsLocation>
        <content><![CDATA[Lindiwe Sisulu, KZN]]></content>
    </gviSms>

    smsDateTime: The date and time when the original SMS arrived at GVI's SMS gateway.
    gatewayIdentifier: Identifies the network and the rate of the SMS.
    cellNumber: The number (in international MSISDN format) of the mobile phone that sent the SMS.
    smsLocation: The short code to which the SMS was sent.
    content: The message text of the SMS message.
    """
    if request.method == "POST":
        raw_xml = request.raw_post_data
        root = ET.fromstring(raw_xml)
        if root.tag == 'gviSms':
            date_string = root.find('smsDateTime').text
            phone_number = root.find('cellNumber').text
            text = unescape(root.find('content').text)

            timestamp = datetime.strptime(date_string, '%y-%m-%dT%H:%M:%S')
            incoming_sms(phone_number, text, GrapevineBackend.get_api_id(), timestamp=timestamp)
        elif root.tag == 'gviSmsResponse':
            date_string = root.find('responseDateTime').text
            phone_number = root.find('recipient/msisdn').text
            resp_type = root.find('responseType').text  # receipt, reply or error
            status_code = root.find('status/code').text
            if status_code == '-1':
                fail_reason = root.find('status/reason').text

            if resp_type == 'reply':
                message_text = unescape(root.find('response').text)
                timestamp = datetime.strptime(date_string, '%y-%m-%dT%H:%M:%S')
                incoming_sms(phone_number, message_text, GrapevineBackend.get_api_id(), timestamp=timestamp)

        return HttpResponse()
    else:
        return HttpResponseBadRequest("Bad Request")
