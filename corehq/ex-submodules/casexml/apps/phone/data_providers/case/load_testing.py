from copy import deepcopy

from casexml.apps.phone.data_providers.case.utils import CaseSyncUpdate
from casexml.apps.phone.xml import get_case_element, tostring

from corehq.apps.app_manager.const import USERCASE_TYPE


def transform_loadtest_update(update, factor):
    """
    Returns a new CaseSyncUpdate object (from an existing one) with all the
    case IDs and names mapped to have the factor appended.
    """
    def _map_id(id, count):
        return '{}-{}'.format(id, count)
    case = deepcopy(update.case)
    case.set_case_id(_map_id(case.case_id, factor))
    for index in case.live_indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = '{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)


def get_xml_for_response(case_sync_update, restore_state, total_cases):
    """
    Adds the XML from the case_update to the restore response.
    If factor is > 1 it will append that many updates to the response for load testing purposes.
    """
    current_count = 0
    original_update = case_sync_update
    elements = []
    loadtest_factor = restore_state.get_safe_loadtest_factor(total_cases)
    while current_count < loadtest_factor:
        element = get_case_element(
            case_sync_update.case,
            case_sync_update.required_updates,
            restore_state.version,
        )
        elements.append(tostring(element))
        current_count += 1
        if current_count < loadtest_factor:
            case_sync_update = transform_loadtest_update(
                original_update,
                current_count,
            )
        # only add user case on the first iteration
        if original_update.case.type == USERCASE_TYPE:
            break
    return elements
