from datetime import datetime
from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tasks import deactivate_users_at_location
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    StaticDataSourceProvider,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.util import get_indicator_adapter
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


def get_household_case_ids(domain, location_id):
    return CaseAccessorSQL.get_case_ids_in_domain_by_owners(
        domain, [location_id], case_type=HOUSEHOLD_CASE_TYPE)


def get_household_and_child_case_ids_by_owner(domain, household_case_id, owner_id, case_types=None):
    case_ids = {household_case_id}
    child_cases = get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types)
    child_case_ids = [case.case_id for case in child_cases]
    case_ids.update(child_case_ids)
    return case_ids


def get_household_child_cases_by_owner(domain, household_case_id, owner_id, case_types):
    def get_child_cases(ids):
        return [case for case in
                CaseAccessorSQL.get_reverse_indexed_cases(domain, ids)
                if case.owner_id == owner_id]

    cases = []
    parent_case_ids = [household_case_id]
    while parent_case_ids:
        child_cases = get_child_cases(parent_case_ids)
        if child_cases:
            parent_case_ids = [case.case_id for case in child_cases]
            if case_types:
                cases.extend([case for case in child_cases if case.type in case_types])
            else:
                cases.extend(child_cases)
        else:
            parent_case_ids = None
    return cases


def get_supervisor_id(domain, location_id):
    new_location = SQLLocation.active_objects.select_related('location_type').get(
        domain=domain, location_id=location_id)
    if new_location.location_type.code == AWC_CODE:
        return new_location.parent.location_id


def reassign_household_case(domain, household_case_id, old_owner_id, new_owner_id, supervisor_id,
                            deprecation_time=None):
    if deprecation_time is None:
        deprecation_time = datetime.utcnow()
    case_ids = get_household_and_child_case_ids_by_owner(domain, household_case_id, old_owner_id)
    case_ids.add(household_case_id)
    case_blocks = []
    for case_id in case_ids:
        updates = {
            'location_reassignment_last_owner_id': old_owner_id,
            'location_reassignment_datetime': deprecation_time
        }
        if supervisor_id:
            updates['location_reassignment_last_supervisor_id'] = supervisor_id
        case_block = CaseBlock(case_id,
                               update=updates,
                               owner_id=new_owner_id,
                               user_id=SYSTEM_USER_ID)
        case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
        case_blocks.append(case_block)
    if case_blocks:
        submit_case_blocks(case_blocks, domain, user_id=SYSTEM_USER_ID)
        process_ucr_changes(domain, case_ids)


def process_ucr_changes(domain, case_ids):
    cases = CaseAccessorSQL.get_cases(case_ids)
    docs = [case.to_json() for case in cases]
    data_source_providers = [DynamicDataSourceProvider(), StaticDataSourceProvider()]

    all_configs = [
        source
        for provider in data_source_providers
        for source in provider.by_domain(domain)
    ]

    adapters = [
        get_indicator_adapter(config, raise_errors=True, load_source='location_reassignment')
        for config in all_configs
    ]

    async_configs_by_doc_id = {}
    for doc in docs:
        eval_context = EvaluationContext(doc)
        for adapter in adapters:
            if adapter.config.filter(doc, eval_context):
                async_configs_by_doc_id[doc['_id']].append(adapter.config._id)
                rows_to_save = adapter.get_all_values(doc, eval_context)
                if rows_to_save:
                    adapter.save_rows(rows_to_save, reassigning_cases=True)
                else:
                    adapter.delete(doc, reassigning_cases=True)
