import re
from datetime import datetime
from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.core.mail.message import EmailMessage
from django.template.defaultfilters import linebreaksbr

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.icds.location_reassignment.const import (
    AWC_CODE,
    CASE_TYPES_TO_IGNORE,
    HOUSEHOLD_CASE_TYPE,
)


def get_case_ids_for_reassignment(domain, location_id):
    """
    :return: for cases that belong to location_id return
    a dict mapping for all case ids under a household id and
    a list of all other case ids
    """
    all_case_ids = CaseAccessorSQL.get_case_ids_in_domain_by_owners(domain, [location_id])
    all_cases = CaseAccessors(domain).get_cases(all_case_ids)
    other_case_ids = set([case.case_id for case in all_cases if case.type not in CASE_TYPES_TO_IGNORE])
    child_case_ids_per_household_id = {}
    for household_case_id in get_household_case_ids(domain, location_id):
        household_child_case_ids = get_household_child_case_ids_by_owner(
            domain, household_case_id, location_id)
        other_case_ids.remove(household_case_id)
        other_case_ids = other_case_ids - set(household_child_case_ids)
        child_case_ids_per_household_id[household_case_id] = household_child_case_ids
    return child_case_ids_per_household_id, list(other_case_ids)


def get_household_case_ids(domain, location_id):
    return CaseAccessorSQL.get_case_ids_in_domain_by_owners(
        domain, [location_id], case_type=HOUSEHOLD_CASE_TYPE)


def get_household_child_case_ids_by_owner(domain, household_case_id, owner_id, case_types=None):
    child_cases = get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types)
    child_case_ids = [case.case_id for case in child_cases]
    return child_case_ids


def get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types=None):
    """
    iterate child cases recursively and then filter out cases owned by the owner id
    """
    def get_child_cases(ids, exclude_ids):
        return [case for case in
                CaseAccessorSQL.get_reverse_indexed_cases(domain, ids)
                if case.case_id not in exclude_ids]

    # keep a list of case ids already iterated to avoid duplicates
    iterated_case_ids = set()
    cases = []
    parent_case_ids = [household_case_id]
    while parent_case_ids:
        child_cases = get_child_cases(parent_case_ids, iterated_case_ids)
        if child_cases:
            child_case_ids = [case.case_id for case in child_cases]
            iterated_case_ids.update(child_case_ids)
            if case_types:
                cases.extend([case for case in child_cases
                              if case.type in case_types and case.owner_id == owner_id])
            else:
                cases.extend(child_cases)
            parent_case_ids = child_case_ids
        else:
            parent_case_ids = None
    return cases


def get_supervisor_id(domain, location_id):
    # get archived/unarchived location's supervisor id
    new_location = SQLLocation.objects.select_related('location_type').get(
        domain=domain, location_id=location_id)
    if new_location.location_type.code == AWC_CODE:
        return new_location.parent.location_id


def reassign_household(domain, household_case_id, old_owner_id, new_owner_id, supervisor_id,
                       deprecation_time=None, household_child_case_ids=None):
    from custom.icds.location_reassignment.tasks import process_ucr_changes
    if deprecation_time is None:
        deprecation_time = datetime.utcnow()
    if household_child_case_ids:
        case_ids = household_child_case_ids
    else:
        case_ids = get_household_child_case_ids_by_owner(domain, household_case_id, old_owner_id)
    case_ids.append(household_case_id)
    case_blocks = []
    for case_id in case_ids:
        updates = {
            'location_reassignment_last_owner_id': old_owner_id,
            'location_reassignment_datetime': deprecation_time
        }
        if supervisor_id:
            updates['location_reassignment_last_supervisor_id'] = supervisor_id
        case_block = CaseBlock.deprecated_init(case_id,
                               update=updates,
                               owner_id=new_owner_id,
                               user_id=SYSTEM_USER_ID)
        case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
        case_blocks.append(case_block)
    if case_blocks:
        submit_case_blocks(case_blocks, domain, user_id=SYSTEM_USER_ID)
    process_ucr_changes.delay(domain, case_ids)


def reassign_cases(domain, case_ids, new_owner_id):
    case_blocks = []
    for case_id in case_ids:
        case_block = CaseBlock.deprecated_init(case_id,
                               owner_id=new_owner_id,
                               user_id=SYSTEM_USER_ID)
        case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
        case_blocks.append(case_block)
    if case_blocks:
        submit_case_blocks(case_blocks, domain, user_id=SYSTEM_USER_ID)


def split_location_name_and_site_code(name):
    # Location Name [location code]
    pattern = r"(.+)\s*\[(.+)\]"
    match = re.match(pattern, name)
    if match:
        return match.groups()
    return name, None


def append_location_name_and_site_code(name, site_code):
    return f"{name.rstrip()} [{site_code}]"


def notify_failure(e, subject, email, uploaded_filename):
    notify_success(
        subject=subject,
        body=linebreaksbr(
            f"The request could not be completed for file {uploaded_filename}. Something went wrong.\n"
            f"Error raised : {e}.\n"
            "Please report an issue if needed."
        ),
        email=email
    )


def notify_success(subject, body, email, filestream=None, filename=None):
    email_message = EmailMessage(
        subject=subject,
        body=linebreaksbr(body),
        to=[email],
        from_email=settings.DEFAULT_FROM_EMAIL
    )
    if filestream and filename:
        email_message.attach(filename=filename, content=filestream.read())
    email_message.content_subtype = "html"
    email_message.send()
