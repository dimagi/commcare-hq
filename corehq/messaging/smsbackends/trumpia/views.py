from xml.etree import cElementTree as ElementTree

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse

from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.trumpia.models import TrumpiaBackend


class TrumpiaIncomingView(IncomingBackendView):
    urlname = 'trumpia_sms_in'

    @property
    def backend_class(self):
        return TrumpiaBackend

    def get(self, request, api_key, *args, **kwargs):
        xml = request.GET.get("xml")
        if xml is None:
            # https://classic.trumpia.com/api/inbound-push.php
            # Please note that the API server has an activity URL
            # checker in place. This URL checker will send empty HTTP
            # GETs/POSTs to see if a URL set is active. Please return a
            # status of 200OK when an empty GET/POST is received.
            return HttpResponse(status=200)
        data = parse_incoming(xml)
        phone_number = data.get("PHONENUMBER")
        text = data.get("CONTENTS")
        if not phone_number or not text:
            return HttpResponseBadRequest("PHONENUMBER or CONTENTS are missing")
        phone_number = add_nanp_prefix(phone_number)
        sms = incoming(
            phone_number,
            text,
            TrumpiaBackend.get_api_id(),
            domain_scope=self.domain,
            backend_message_id=data.get("PUSH_ID"),
            backend_id=self.backend_couch_id,
        )
        return JsonResponse({"status": "OK", "message_id": sms.couch_id})

    def post(self, request, api_key, *args, **kwargs):
        return self.get(request, api_key, *args, **kwargs)


def parse_incoming(xml):
    """Parse incoming message XML

    Sample input:

        <?xml version="1.0" encoding="UTF-8" ?>
        <TRUMPIA>
            <PUSH_ID>1234561234567asdf123</PUSH_ID>
            <INBOUND_ID>9996663330001</INBOUND_ID>
            <SUBSCRIPTION_UID>987987987980</SUBSCRIPTION_UID>
            <PHONENUMBER>7777722222</PHONENUMBER>
            <KEYWORD>REPLY</KEYWORD>
            <CONTENTS><![CDATA[A sample reply message]]></CONTENTS>
            <ATTACHMENT />
        </TRUMPIA>

    Sample output:

        {
            "PUSH_ID": "1234561234567asdf123",
            "INBOUND_ID": "9996663330001",
            "SUBSCRIPTION_UID": "987987987980",
            "PHONENUMBER": "7777722222",
            "KEYWORD": "REPLY",
            "CONTENTS": "A sample reply message",
            "ATTACHMENT": "",
        }

    :returns: Dict of parsed data.
    """
    try:
        root = ElementTree.fromstring(xml)
    except (TypeError, ElementTree.ParseError):
        return {}
    data = {}
    for element in root:
        data[element.tag] = element.text
    return data


def add_nanp_prefix(number, region_code="1"):
    """Add country code to North American Numbering Plan phone number

    https://en.wikipedia.org/wiki/National_conventions_for_writing_telephone_numbers
    #United_States,_Canada,_and_other_NANP_countries
    """
    if len(number) == 10 and number[0] not in "01":
        number = region_code + number
    return number
