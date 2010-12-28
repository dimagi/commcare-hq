import logging
import urllib2
from datetime import datetime
from django.conf import settings
from corehq.apps.sms.models import MessageLog, OUTGOING

def send_sms(domain, id, phone_number, text):
    # temporary placeholder
    print "sending %s to %s" % (text, phone_number)
    logging.debug('Sending message: %s' % text)
    context = {'message':text,
               'phone_number':phone_number}
    url = "%s?%s" % (settings.SMS_GATEWAY_URL, settings.SMS_GATEWAY_PARAMS % context)
    try:
        response = urllib2.urlopen(url)
    except Exception, e:
        return False
    msg = MessageLog(domain=domain,
                     couch_recipient=id, 
                     phone_number=phone_number,
                     direction=OUTGOING,
                     date = datetime.now(),
                     text = text)
    msg.save()
    return True



