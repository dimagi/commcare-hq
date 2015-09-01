from datetime import datetime
import logging
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.api import incoming
from corehq.apps.sms.mixin import SMSBackend
from corehq.util.timezones.conversions import UserTime
from urllib2 import urlopen
from urllib import urlencode
import pytz
from dimagi.ext.couchdbkit import *
from commcarehq.messaging.smsbackends.unicel.forms import UnicelBackendForm
from django.conf import settings

OUTBOUND_URLBASE = "http://www.unicel.in/SendSMS/sendmsg.php"

class InboundParams(object):
    """
    A constant-defining class for incoming sms params
    """
    SENDER = "send"
    MESSAGE = "msg"

    # 1 if message is multipart message, 0 otherwise
    UDHI = "UDHI"

    # gateway message id
    MID = "MID"

    # 8 if message is a unicode hex string, 0 if ascii
    DCS = "DCS"


class OutboundParams(object):
    """
    A constant-defining class for outbound sms params
    """
    SENDER = "send"
    MESSAGE = "msg"
    USERNAME = "uname"
    PASSWORD = "pass"
    DESTINATION = "dest"

# constant additional parameters when sending a unicode message
UNICODE_PARAMS = [("udhi", 0),
                  ("dcs", 8)]

class UnicelBackend(SMSBackend):
    username = StringProperty()
    password = StringProperty()
    sender = StringProperty()

    @classmethod
    def get_api_id(cls):
        return "UNICEL"

    @classmethod
    def get_generic_name(cls):
        return "Unicel"

    @classmethod
    def get_template(cls):
        return "unicel/backend.html"

    @classmethod
    def get_form_class(cls):
        return UnicelBackendForm

    def send(self, message, delay=True, *args, **kwargs):
        """
        Send an outbound message using the Unicel API
        """
        
        phone_number = clean_phone_number(message.phone_number).replace("+", "")
        params = [(OutboundParams.DESTINATION, phone_number),
                  (OutboundParams.USERNAME, self.username),
                  (OutboundParams.PASSWORD, self.password),
                  (OutboundParams.SENDER, self.sender)]
        try:
            text = str(message.text)
            # it's ascii
            params.append((OutboundParams.MESSAGE, text))
        except UnicodeEncodeError:
            params.extend(UNICODE_PARAMS)
            encoded = message.text.encode("utf_16_be").encode("hex").upper()
            params.append((OutboundParams.MESSAGE, encoded))

        try:
            data = urlopen('%s?%s' % (OUTBOUND_URLBASE, urlencode(params)),
                timeout=settings.SMS_GATEWAY_TIMEOUT).read()
        except Exception:
            data = None

        return data


def create_from_request(request):
    """
    From an inbound request (representing an incoming message),
    create a message (log) object with the right fields populated.
    """
    sender = request.REQUEST[InboundParams.SENDER]
    message = request.REQUEST[InboundParams.MESSAGE]

    if len(sender) == 10:
        # add india country code
        sender = '91' + sender

    is_unicode = request.REQUEST.get(InboundParams.DCS, "") == "8"
    if is_unicode:
        message = message.decode("hex").decode("utf_16_be")

    backend_message_id = request.REQUEST.get(InboundParams.MID, None)

    log = incoming(sender, message, UnicelBackend.get_api_id(), backend_message_id=backend_message_id)

    return log

