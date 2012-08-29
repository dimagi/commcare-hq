import logging
from urllib import urlencode
from urllib2 import urlopen

API_ID = "TROPO"

def send(msg, delay=True, *args, **kwargs):
    """
    Expected kwargs:
        messaging_token
    """
    phone_number = msg.phone_number
    if phone_number[0] != "+":
        phone_number = "+" + phone_number
    params = urlencode({
        "action" : "create"
       ,"token" : kwargs["messaging_token"]
       ,"numberToDial" : phone_number
       ,"msg" : msg.text
       ,"_send_sms" : "true"
    })
    url = "https://api.tropo.com/1.0/sessions?%s" % params
    response = urlopen(url).read()
    msg.save()
    try:
        # attempt to bill client
        from hqbilling.tasks import bill_client_for_sms
        from hqbilling.models import TropoSMSBillable
        if delay:
            bill_client_for_sms.delay(TropoSMSBillable, msg.get_id, **dict(response=response))
        else:
            bill_client_for_sms(TropoSMSBillable, msg.get_id, **dict(response=response))
    except Exception as e:
        logging.debug("TROPO API contacted, errors in billing. Error: %s" % e)

    return response

