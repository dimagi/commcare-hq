from corehq.apps.grapevine.api import GrapevineBackend
from corehq.apps.sms.api import incoming as incoming_sms
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from xml.etree import ElementTree as ET
from xml.sax.saxutils import unescape

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'

@csrf_exempt
def sms_in(request):
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
    if request.method == "POST":
        raw_xml = request.POST['XML']
        root = ET.fromstring(raw_xml)
        if root.tag == 'gviSms':
            date_string = root.find('smsDateTime').text
            phone_number = root.find('cellNumber').text
            content_text = root.find('content').text
            text = unescape(content_text) if content_text else ''

            incoming_sms(phone_number, text, GrapevineBackend.get_api_id())
        elif root.tag == 'gviSmsResponse':
            date_string = root.find('responseDateTime').text
            phone_number = root.find('recipient/msisdn').text
            resp_type = root.find('responseType').text  # receipt, reply or error

            if resp_type == 'reply':
                response_text = root.find('response').text
                message_text = unescape(response_text) if response_text else ''
                incoming_sms(phone_number, message_text, GrapevineBackend.get_api_id())

        return HttpResponse()
    else:
        return HttpResponseBadRequest("Bad Request")
