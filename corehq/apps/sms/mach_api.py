import logging
from corehq.apps.sms.util import clean_outgoing_sms_text, create_billable_for_sms
import urllib
from django.conf import settings
import urllib2

API_ID = "MACH"

DEFAULT_SENDER_ID = "DIMAGI"

def send(msg, delay=True, *args, **kwargs):
    """
    Sends a message via mach's API
    """
    outgoing_sms_text = clean_outgoing_sms_text(msg.text)
    context = {
        'message': outgoing_sms_text,
        'phone_number': urllib.quote(msg.phone_number),
        'sender_id': urllib.quote(kwargs.get("sender_id", DEFAULT_SENDER_ID)),
    }
    url = "%s?%s" % (settings.SMS_GATEWAY_URL, settings.SMS_GATEWAY_PARAMS % context)
    # just opening the url is enough to send the message
    # TODO, check response
    resp = urllib2.urlopen(url).read()
    msg.save()

    create_billable_for_sms(msg, API_ID, delay=delay, response=resp)

    return resp
