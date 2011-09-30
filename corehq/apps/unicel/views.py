from datetime import datetime, date, timedelta
from django.http import HttpResponse
from corehq.apps.sms.util import domains_for_phone, users_for_phone
from corehq.apps.sms.models import MessageLog

class Params(object):
    """
    A constant-defining class  
    """
    SENDER = "send"
    MESSAGE = "msg"
    TIMESTAMP = "stime"

DATE_FORMAT = "%m/%d/%Y %H:%M:%S %p"

def incoming(request):
    """
    The inbound endpoint for UNICEL's API.
    """
    # for now just save this information in the message log and return
    sender = request.REQUEST.get(Params.SENDER, "")
    message = request.REQUEST.get(Params.MESSAGE, "")
    timestamp = request.REQUEST.get(Params.TIMESTAMP, "")
    
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
                                    direction="I",
                                    date=actual_timestamp,
                                    text=message,
                                    domain=domain)
    
    return HttpResponse("Received: %s" % log)