from xml.etree import cElementTree as ElementTree

from django.conf import settings

from celery.task import task

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tasks import deactivate_users_at_location
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from custom.icds.location_reassignment.const import (
    AWC_CODE,
    HOUSEHOLD_CASE_TYPE,
)
from custom.icds.location_reassignment.models import Transition


def deprecate_locations(domain, old_locations, new_locations, operation):
    """
    add metadata on locations
    on old locations, add
    1. DEPRECATED_TO: [list] would be a single location except in case of a split
    2. DEPRECATION_OPERATION: this location was deprecated by a merge/split/extract/move operation
    3. DEPRECATED_AT: [dict] new location id mapped to the timestamp of deprecation performed
    for new locations location
    1. DEPRECATES: [list] append this location id on it. This would be more than one location in case of merge
    :param domain: domain name
    :param old_locations: the locations to deprecate
    :param new_locations: the location that deprecates these location
    :param operation: the operation being performed, split/merge/move/extract
    :return: errors in case of failure
    """
    transition = Transition(domain, operation, old_locations, new_locations)
    if transition.valid():
        transition.perform()
        for old_location in old_locations:
            deactivate_users_at_location(old_location.location_id)
    return transition.errors


@task(queue=settings.CELERY_LOCATION_REASSIGNMENT_QUEUE)
def reassign_cases(domain, old_location_id, new_location_id, deprecation_time):
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
        case_ids = get_household_and_child_cases_by_owner(domain, household_case_id, old_location_id)
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


def get_household_and_child_cases_by_owner(domain, household_case_id, owner_id):
    def get_child_case_ids(ids):
        return [case.case_id for case in CaseAccessorSQL.get_reverse_indexed_cases(domain, ids)
                if case.owner_id == owner_id]

    all_child_case_ids = {household_case_id}
    case_ids = [household_case_id]

    while case_ids:
        child_case_ids = get_child_case_ids(case_ids)
        if child_case_ids:
            all_child_case_ids.update(child_case_ids)
            case_ids = child_case_ids
        else:
            case_ids = None
    return all_child_case_ids
