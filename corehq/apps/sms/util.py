import re
import urllib

from dimagi.utils.couch.database import get_db
from corehq.apps.users.models import CouchUser


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
    view_results = get_db().view("sms/phones_to_domains", key=phone)
    return [row["value"] for row in view_results]

def users_for_phone(phone):
    """
    Get users attached to a phone number
    """
    view_results = get_db().view("sms/phones_to_domains", key=phone)
    user_ids = set([row["id"] for row in view_results])
    return [CouchUser.get(id) for id in user_ids]


def format_message_list(message_list):
    """
    question = message_list[-1]
    if len(question) > 160:
        return question[0:157] + "..."
    else:
        extra_space = 160 - len(question)
        message_start = ""
        if extra_space > 3:
            for msg in message_list[0:-1]:
                message_start += msg + ". "
            if len(message_start) > extra_space:
                message_start = message_start[0:extra_space-3] + "..."
        return message_start + question
    """
    # Some gateways (yo) allow a longer message to be sent and handle splitting it up on their end, so for now just join all messages together
    return " ".join(message_list)

