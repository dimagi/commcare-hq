from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.core.mail.message import EmailMessage

from celery.task import task

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import SYSTEM_USER_ID, normalize_username
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from custom.icds.location_reassignment.const import (
    AWC_CODE,
    HOUSEHOLD_CASE_TYPE,
)
from custom.icds.location_reassignment.exceptions import InvalidUserTransition
from custom.icds.location_reassignment.processor import Processor
from custom.icds.location_reassignment.utils import (
    get_household_and_child_case_ids_by_owner,
)


@task
def process_location_reassignment(domain, transitions, new_location_details, user_transitions,
                                  site_codes, user_email):
    try:
        Processor(domain, transitions, new_location_details, user_transitions, site_codes).process()
    except Exception as e:
        email = EmailMessage(
            subject='[{}] - Location Reassignment Failed'.format(settings.SERVER_ENVIRONMENT),
            body="The request could not be completed. Something went wrong. "
                 "Error raised : {}. "
                 "Please report an issue if needed.".format(e),
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()
        raise e
    else:
        email = EmailMessage(
            subject='[{}] - Location Reassignment Completed'.format(settings.SERVER_ENVIRONMENT),
            body="The request has been successfully completed.",
            to=[user_email],
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.send()


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def reassign_household_and_child_cases_for_owner(domain, old_location_id, new_location_id, deprecation_time):
    """
    finds all household cases assigned to the old location and then
    reassign the household case and all its child cases to new location
    """
    supervisor_id = ""
    new_location = SQLLocation.active_objects.select_related('location_type').get(
        domain=domain, location_id=new_location_id)
    if new_location.location_type.code == AWC_CODE:
        supervisor_id = new_location.parent.location_id
    household_case_ids = CaseAccessorSQL.get_case_ids_in_domain_by_owners(
        domain, [old_location_id], case_type=HOUSEHOLD_CASE_TYPE)

    for household_case_id in household_case_ids:
        case_ids = get_household_and_child_case_ids_by_owner(domain, household_case_id, old_location_id)
        case_ids.add(household_case_id)
        case_blocks = []
        for case_id in case_ids:
            case_block = CaseBlock(case_id,
                                   update={
                                       'location_reassignment_last_owner_id': old_location_id,
                                       'location_reassignment_datetime': deprecation_time,
                                       'location_reassignment_last_supervisor_id': supervisor_id
                                   },
                                   owner_id=new_location_id,
                                   user_id=SYSTEM_USER_ID)
            case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
            case_blocks.append(case_block)
        if case_blocks:
            submit_case_blocks(case_blocks, domain, user_id=SYSTEM_USER_ID)


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def update_usercase(domain, old_username, new_username):
    if "@" not in old_username:
        old_username = normalize_username(old_username, domain)
    if "@" not in new_username:
        new_username = normalize_username(new_username, domain)
    old_user = CouchUser.get_by_username(old_username)
    new_user = CouchUser.get_by_username(new_username)
    if old_user and new_user and old_user.is_commcare_user() and new_user.is_commcare_user():
        old_user_usercase = old_user.get_usercase()
        new_user_usercase = new_user.get_usercase()
        # pick values that are not already present on the new user's usercase, populated already via HQ
        updates = {}
        for key in set(old_user_usercase.case_json.keys()) - set(new_user_usercase.case_json.keys()):
            updates[key] = old_user_usercase.case_json[key]
        if updates:
            case_block = CaseBlock(new_user_usercase.case_id,
                                   update=old_user_usercase.case_json,
                                   user_id=SYSTEM_USER_ID)
            submit_case_blocks([case_block], domain, user_id=SYSTEM_USER_ID)
    else:
        raise InvalidUserTransition("Invalid Transition with old user %s and new user %s" % (
            old_username, new_username
        ))
