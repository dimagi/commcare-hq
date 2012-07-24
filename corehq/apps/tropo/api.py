import logging
from urllib import urlencode
from urllib2 import urlopen

API_ID = "TROPO"

def send(msg, *args, **kwargs):
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
    print response

    try:
        # attempt to bill client
        from hqpayments.tasks import bill_client_for_sms
        bill_client_for_sms('TropoSMSBillableItem', msg)
    except Exception as e:
        logging.debug("UNICEL API contacted, errors in billing. Error: %s" % e)

