from datetime import datetime, date, timedelta
import logging
from corehq.apps.sms.util import clean_phone_number, clean_outgoing_sms_text, create_billable_for_sms
from corehq.apps.sms.api import incoming
from django.conf import settings
from urllib2 import urlopen
from urllib import urlencode
import pytz

API_ID = "UNICEL"

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

def _check_environ():
    if not hasattr(settings, "UNICEL_CONFIG") \
    or not settings.UNICEL_CONFIG.get("username", "") \
    or not settings.UNICEL_CONFIG.get("password", "") \
    or not settings.UNICEL_CONFIG.get("sender", ""):
        raise Exception("Bad Unicel configuration. You must set a "
                        "username and password in a settings variable "
                        "called UNICEL_CONFIG to use this backend")

def _config():
    _check_environ()
    return settings.UNICEL_CONFIG

DATE_FORMAT = "%m/%d/%y %I:%M:%S %p"
DATE_FORMAT2 = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT3 = "%Y-%m-%d%%20%H:%M:%S"

def convert_timestamp(timestamp):
    for format in [DATE_FORMAT, DATE_FORMAT2, DATE_FORMAT3]:
        try:
            actual_timestamp = datetime.strptime(timestamp, format)
        except ValueError:
            pass
        else:
            return pytz.timezone('Asia/Kolkata').localize(actual_timestamp).astimezone(pytz.utc)
    raise ValueError('could not parse unicel inbound timestamp [%s]' % timestamp)

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
    if timestamp:
        try:
            actual_timestamp = convert_timestamp(timestamp)
        except ValueError:
            logging.warning('could not parse unicel inbound timestamp [%s]' % timestamp)
            actual_timestamp = None

    # not sure yet if this check is valid
    is_unicode = request.REQUEST.get(InboundParams.UDHI, "") == "1"
    if is_unicode:
        message = message.decode("hex").decode("utf_16_be")

    log = incoming(sender, message, API_ID, timestamp=actual_timestamp, delay=delay)

    return log

def receive_phone_number():
    return _config().get('receive_phone')

def send(message, delay=True):
    """
    Send an outbound message using the Unicel API
    """
    config = _config()

    phone_number = clean_phone_number(message.phone_number).replace("+", "")
    # these are shared regardless of API
    params = [(OutboundParams.DESTINATION, phone_number),
              (OutboundParams.USERNAME, config["username"]),
              (OutboundParams.PASSWORD, config["password"]),
              (OutboundParams.SENDER, config["sender"])]
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
    message.save()

    create_billable_for_sms(message, API_ID, delay=delay, response=data)

    return data



