from corehq.apps.sms.util import clean_outgoing_sms_text
import urllib
from django.conf import settings
import urllib2


def send(msg):
    """
    Sends a message via mach's API
    """
    outgoing_sms_text = clean_outgoing_sms_text(msg.text)
    context = {
        'message': outgoing_sms_text,
        'phone_number': urllib.quote(msg.phone_number),
    }
    url = "%s?%s" % (settings.SMSGATEWAY_URL, settings.SMS_GATEWAY_PARAMS % context)
    # just opening the url is enough to send the message
    # TODO, check response
    resp = urllib2.urlopen(url)
    
    
