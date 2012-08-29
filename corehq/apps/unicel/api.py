from datetime import datetime, date, timedelta
import logging
from corehq.apps.sms.models import SMSLog, INCOMING
from corehq.apps.sms.util import domains_for_phone, users_for_phone,\
    clean_phone_number, clean_outgoing_sms_text
from django.conf import settings
from urllib2 import urlopen
from urllib import urlencode

API_ID = "UNICEL"

OUTBOUND_URLBASE = "http://www.unicel.in/SendSMS/sendmsg.php"

class InboundParams(object):
    """
    A constant-defining class for incoming sms params
    """
    SENDER = "sender"
    MESSAGE = "msg"
    TIMESTAMP = "stime"
    UDHI = "udhi"
    DCS = "dcs"
    
class OutboundParams(object):    
    """
    A constant-defining class for outbound sms params
    """
    SENDER = "sender"
    MESSAGE = "msg"
    USERNAME = "uname"
    PASSWORD = "pass"
    DESTINATION = "dest"

# constant additional parameters when sending a unicode message
UNICODE_PARAMS = [("udhi", 0),
                  ("dcs", 8)]

DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"

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

def create_from_request(request, delay=True):
    """
    From an inbound request (representing an incoming message), 
    create a message (log) object with the right fields populated.
    """
    sender = request.REQUEST.get(InboundParams.SENDER, "")
    message = request.REQUEST.get(InboundParams.MESSAGE, "")
    timestamp = request.REQUEST.get(InboundParams.TIMESTAMP, "")
    # parse date or default to current utc time
    actual_timestamp = datetime.strptime(timestamp, DATE_FORMAT) \
                            if timestamp else datetime.utcnow()
    
    # not sure yet if this check is valid
    is_unicode = request.REQUEST.get(InboundParams.UDHI, "") == "1"
    if is_unicode:
        message = message.decode("hex").decode("utf_16_be")
    # if you don't have an exact match for either of these fields, save nothing
    domains = domains_for_phone(sender)
    domain = domains[0] if len(domains) == 1 else "" 
    recipients = users_for_phone(sender)
    recipient = recipients[0].get_id if len(recipients) == 1 else "" 
    
    log = SMSLog(couch_recipient=recipient,
                        couch_recipient_doc_type="CouchUser",
                        phone_number=sender,
                        direction=INCOMING,
                        date=actual_timestamp,
                        text=message,
                        domain=domain,
                        backend_api=API_ID)
    log.save()

    try:
        # attempt to bill client
        from hqbilling.tasks import bill_client_for_sms
        from hqbilling.models import UnicelSMSBillable
        if delay:
            bill_client_for_sms.delay(UnicelSMSBillable, log._id)
        else:
            bill_client_for_sms(UnicelSMSBillable, log._id)
    except Exception as e:
        logging.debug("UNICEL API contacted, errors in billing. Error: %s" % e)

    return log
    

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
    try:
        # attempt to bill client
        from hqbilling.tasks import bill_client_for_sms
        from hqbilling.models import UnicelSMSBillable
        if delay:
            bill_client_for_sms.delay(UnicelSMSBillable, message.get_id, **dict(response=data))
        else:
            bill_client_for_sms(UnicelSMSBillable, message.get_id, **dict(response=data))
    except Exception as e:
        logging.debug("UNICEL API contacted, errors in billing. Error: %s" % e)

    return data

    
    
