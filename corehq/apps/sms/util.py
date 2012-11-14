import re
import urllib
import uuid
import datetime

from django.conf import settings
from dimagi.utils.couch.database import get_db
from corehq.apps.users.models import CouchUser
from django.template.loader import render_to_string
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.sms.mixin import MobileBackend

from xml.etree.ElementTree import XML, tostring
from dimagi.utils.parsing import json_format_datetime

def get_outbound_sms_backend(phone_number, domain=None):
    """
    Get the appropriate outbound SMS backend to send to a
    particular phone_number
    """
    # TODO: support domain-specific settings

    backend_mapping = sorted(settings.SMS_BACKENDS.iteritems(),
                             key=lambda (prefix, backend): len(prefix),
                             reverse=True)
    for prefix, backend in backend_mapping:
        if phone_number.startswith('+' + prefix):
            return load_backend(backend)
    raise RuntimeError('no suitable backend found for phone number %s' % phone_number)

def load_backend(tag):
    """look up a mobile backend
    for 'old-style' backends, create a virtual backend record
    wrapping the backend module
    """

    # new-style backend
    try:
        return MobileBackend.get(tag)
    except:
        pass

    # old-style backend

    # hard-coded old-style backends with new-style IDs
    # once the backend migration is complete, these backends
    # should exist in couch
    transitional = {
        'MOBILE_BACKEND_MACH': 'corehq.apps.sms.mach_api',
        'MOBILE_BACKEND_UNICEL': 'corehq.apps.unicel.api',
        'MOBILE_BACKEND_TEST': 'corehq.apps.sms.test_backend',
        # tropo?
    }
    try:
        module = transitional[tag]
    except KeyError:
        module = tag

    return MobileBackend(
        _id=tag,
        outbound_module=module,
        description='virtual backend for %s' % tag,
    )

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
        "task_activation_date" : json_format_datetime(task_activation_datetime),
        "parent" : parent_case,
    }
    case_block = render_to_string("sms/xml/create_task.xml", context)
    case_block = tostring(XML(case_block)) # Ensure the XML is formatted properly, an exception is raised if not
    submit_case_blocks(case_block, parent_case.domain)


