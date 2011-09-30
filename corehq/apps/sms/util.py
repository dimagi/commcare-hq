import re
import logging
import urllib
import urllib2
from datetime import datetime

from django.conf import settings

from corehq.apps.sms.models import MessageLog, OUTGOING
from dimagi.utils.couch.database import get_db
from corehq.apps.users.models import CouchUser

def send_sms(domain, id, phone_number, text):
    """
    return False if sending the message failed. 
    """
    logging.debug('Sending message: %s' % text)
    phone_number = clean_phone_number(phone_number)
    outgoing_sms_text = clean_outgoing_sms_text(text)
    # print "sending %s to %s" % (text, phone_number)
    context = {
        'message': outgoing_sms_text,
        'phone_number': urllib.quote(phone_number),
    }
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

def clean_phone_number(text):
    """
    strip non-numeric characters and add '%2B' at the front
    """
    non_decimal = re.compile(r'[^\d.]+')
    plus = '+'
    cleaned_text = "%s%s" % (plus, non_decimal.sub('', text))
    return cleaned_text

def clean_outgoing_sms_text(text):
    try:
        return urllib.quote(text)
    except KeyError:
        return urllib.quote(text.encode('utf-8'))

def domains_for_phone(phone):
    """
    Get domains attached to a phone number
    """
    view_results = get_db().view("sms/phones_to_domains")
    return [row["value"] for row in view_results]

def users_for_phone(phone):
    """
    Get users attached to a phone number
    """
    view_results = get_db().view("sms/phones_to_domains")
    user_ids = set([row["id"] for row in view_results])
    return [CouchUser.get(id) for id in user_ids]