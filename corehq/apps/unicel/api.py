from datetime import datetime, date, timedelta
from corehq.apps.sms.models import MessageLog, INCOMING
from corehq.apps.sms.util import domains_for_phone, users_for_phone,\
    clean_phone_number
from django.conf import settings
from urllib2 import urlopen
from urllib import urlencode

OUTBOUND_URLBASE = "http://www.unicel.in/SendSMS/sendmsg.php"

class InboundParams(object):
    """
    A constant-defining class for incoming sms params
    """
    SENDER = "sender"
    MESSAGE = "msg"
    TIMESTAMP = "stime"
    
class OutboundParams(object):    
    """
    A constant-defining class for outbound sms params
    """
    SENDER = "sender"
    MESSAGE = "msg"
    USERNAME = "uname"
    PASSWORD = "pass"
    DESTINATION = "dest"
    
    
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

def create_from_request(request):
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
    
    # if you don't have an exact match for either of these fields, save nothing
    domains = domains_for_phone(sender)
    domain = domains[0] if len(domains) == 1 else "" 
    recipients = users_for_phone(sender)
    recipient = recipients[0] if len(recipients) == 1 else "" 
    
    log = MessageLog.objects.create(couch_recipient=recipient,
                                    phone_number=sender,
                                    direction=INCOMING,
                                    date=actual_timestamp,
                                    text=message,
                                    domain=domain)
    
    return log
    

def send(message):
    """
    Send an outbound message using the Unicel API
    """
    config = _config()
    
    phone_number = clean_phone_number(message.phone_number).replace("+", "")
    params =  urlencode([(OutboundParams.DESTINATION, phone_number),
                         (OutboundParams.MESSAGE, message.text),
                         (OutboundParams.USERNAME, config["username"]),
                         (OutboundParams.PASSWORD, config["password"]),
                         (OutboundParams.SENDER, config["sender"])])
    data = urlopen('%s?%s' % (OUTBOUND_URLBASE, params)).read()
    