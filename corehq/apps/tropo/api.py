import logging
from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.util import create_billable_for_sms

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

    create_billable_for_sms(msg, API_ID, delay=delay, response=response)

    return response

