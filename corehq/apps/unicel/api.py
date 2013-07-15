from datetime import datetime, date, timedelta
import logging
from corehq.apps.sms.util import clean_phone_number, clean_outgoing_sms_text, create_billable_for_sms
from corehq.apps.sms.api import incoming
from corehq.apps.sms.mixin import SMSBackend
from django.conf import settings
from urllib2 import urlopen
from urllib import urlencode
import pytz
from couchdbkit.ext.django.schema import *
from corehq.apps.unicel.forms import UnicelBackendForm

OUTBOUND_URLBASE = "http://www.unicel.in/SendSMS/sendmsg.php"

class InboundParams(object):
    """
    A constant-defining class for incoming sms params
    """
    SENDER = "send"
    MESSAGE = "msg"
    TIMESTAMP = "stime"
    UDHI = "udhi"
    DCS = "dcs"
    
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

DATE_FORMAT = "%m/%d/%y %I:%M:%S %p"

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
            data = urlopen('%s?%s' % (OUTBOUND_URLBASE, urlencode(params))).read()
        except Exception:
            data = None

        create_billable_for_sms(message, UnicelBackend.get_api_id(), delay=delay, response=data)

        return data

def create_from_request(request, delay=True):
    """
    From an inbound request (representing an incoming message), 
    create a message (log) object with the right fields populated.
    """
    sender = request.REQUEST[InboundParams.SENDER]
    message = request.REQUEST[InboundParams.MESSAGE]
    timestamp = request.REQUEST.get(InboundParams.TIMESTAMP, "")

    if len(sender) == 10:
        # add india country code
        sender = '91' + sender

    # parse date or default to current utc time
    actual_timestamp = None
    if timestamp:
        try:
            actual_timestamp = datetime.strptime(timestamp, DATE_FORMAT)
            actual_timestamp = pytz.timezone('Asia/Kolkata').localize(actual_timestamp).astimezone(pytz.utc)
        except Exception, e:
            logging.warning('could not parse unicel inbound timestamp [%s]' % timestamp)
    
    # not sure yet if this check is valid
    is_unicode = request.REQUEST.get(InboundParams.UDHI, "") == "1"
    if is_unicode:
        message = message.decode("hex").decode("utf_16_be")

    log = incoming(sender, message, UnicelBackend.get_api_id(), timestamp=actual_timestamp, delay=delay)

    return log

