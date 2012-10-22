import re
import urllib
import uuid
import datetime

from dimagi.utils.couch.database import get_db
from corehq.apps.users.models import CouchUser
from django.template.loader import render_to_string
from corehq.apps.hqcase.utils import submit_case_blocks

from xml.etree.ElementTree import XML, tostring

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

# Creates a case by submitting system-generated casexml
def register_sms_contact(domain, case_type, case_name, user_id, contact_phone_number, contact_phone_number_is_verified="1", contact_backend_id=None, language_code=None, time_zone=None):
    utcnow = str(datetime.datetime.utcnow())
    case_id = uuid.uuid3(uuid.NAMESPACE_URL, utcnow)
    date_modified = utcnow
    context = {
        "case_id" : case_id,
        "date_modified" : date_modified,
        "case_type" : case_type,
        "case_name" : case_name,
        "user_id" : user_id,
        "contact_phone_number" : contact_phone_number,
        "contact_phone_number_is_verified" : contact_phone_number_is_verified,
        "contact_backend_id" : contact_backend_id,
        "language_code" : language_code,
        "time_zone" : time_zone
    }
    case_block = render_to_string("sms/xml/register_contact.xml", context)
    case_block = tostring(XML(case_block)) # Ensure the XML is formatted properly, an exception is raised if not
    submit_case_blocks(case_block, domain)

def create_task(parent_case, submitting_user_id, task_owner_id, form_unique_id, task_activation_datetime):
    utcnow = str(datetime.datetime.utcnow())
    subcase_guid = uuid.uuid3(uuid.NAMESPACE_URL, utcnow)
    date_modified = utcnow
    context = {
        "subcase_guid" : subcase_guid,
        "user_id" : submitting_user_id,
        "date_modified" : date_modified,
        "task_owner_id" : task_owner_id,
        "form_unique_id" : form_unique_id,
        "task_activation_date" : str(task_activation_datetime.date()) + "T" + str(task_activation_datetime.time()),
        "parent" : parent_case,
    }
    case_block = render_to_string("sms/xml/create_task.xml", context)
    case_block = tostring(XML(case_block)) # Ensure the XML is formatted properly, an exception is raised if not
    submit_case_blocks(case_block, parent_case.domain)


