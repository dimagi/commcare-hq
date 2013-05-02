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
    context = {
        'phone_number': urllib.quote(msg.phone_number),
        'sender_id': urllib.quote(kwargs.get("sender_id", DEFAULT_SENDER_ID)),
    }
    encoding_param = ""
    try:
        text = msg.text.encode("iso-8859-1")
        context["message"] = clean_outgoing_sms_text(text)
    except UnicodeEncodeError:
        context["message"] = msg.text.encode("utf-16-be").encode("hex")
        encoding_param = "&encoding=ucs"
    url = "%s?%s%s" % (settings.SMS_GATEWAY_URL, settings.SMS_GATEWAY_PARAMS % context, encoding_param)
    # just opening the url is enough to send the message
    # TODO, check response
    resp = urllib2.urlopen(url).read()
    msg.save()

    create_billable_for_sms(msg, API_ID, delay=delay, response=resp)

    return resp
