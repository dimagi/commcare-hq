import logging
from corehq.apps.sms.util import clean_outgoing_sms_text
import urllib
from django.conf import settings
import urllib2

API_ID = "MACH"

def send(msg, delay=True):
    """
    Sends a message via mach's API
    """
    outgoing_sms_text = clean_outgoing_sms_text(msg.text)
    context = {
        'message': outgoing_sms_text,
        'phone_number': urllib.quote(msg.phone_number),
    }
    url = "%s?%s" % (settings.SMS_GATEWAY_URL, settings.SMS_GATEWAY_PARAMS % context)
    # just opening the url is enough to send the message
    # TODO, check response
    resp = urllib2.urlopen(url).read()
    msg.save()
    try:
        # attempt to bill client
        from hqbilling.tasks import bill_client_for_sms
        from hqbilling.models import MachSMSBillable
        if delay:
            bill_client_for_sms.delay(MachSMSBillable, msg.get_id, **dict(response=resp))
        else:
            bill_client_for_sms(MachSMSBillable, msg.get_id, **dict(response=resp))
    except Exception as e:
        logging.debug("MACH API contacted, errors in billing. Error: %s" % e)

    return resp