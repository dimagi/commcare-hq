from __future__ import absolute_import
from __future__ import unicode_literals
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
    for index in case.indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = '{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)


def get_xml_for_response(update, restore_state):
    """
    Adds the XML from the case_update to the restore response.
    If factor is > 1 it will append that many updates to the response for load testing purposes.
    """
    current_count = 0
    original_update = update
    elements = []
    while current_count < restore_state.loadtest_factor:
        element = get_case_element(update.case, update.required_updates, restore_state.version)
        elements.append(tostring(element))
        current_count += 1
        if current_count < restore_state.loadtest_factor:
            update = transform_loadtest_update(original_update, current_count)
        # only add user case on the first iteration
        if original_update.case.type == USERCASE_TYPE:
            break
    return elements
