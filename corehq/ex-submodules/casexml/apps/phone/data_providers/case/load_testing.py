from copy import deepcopy
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.data_providers.case.utils import CaseSyncUpdate
from casexml.apps.phone.xml import get_case_element
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.toggles import ENABLE_LOADTEST_USERS


def get_loadtest_factor(domain, user):
    """
    Gets the loadtest factor for a domain and user. Is always 1 unless
    both the toggle is enabled for the domain, and the user has a non-zero,
    non-null factor set.
    """
    if domain and ENABLE_LOADTEST_USERS.enabled(domain):
        return getattr(user, 'loadtest_factor', 1) or 1
    return 1


def transform_loadtest_update(update, factor):
    """
    Returns a new CaseSyncUpdate object (from an existing one) with all the
    case IDs and names mapped to have the factor appended.
    """
    def _map_id(id, count):
        return u'{}-{}'.format(id, count)
    case = CommCareCase.wrap(deepcopy(update.case._doc))
    case._id = _map_id(case._id, factor)
    for index in case.indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = u'{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)


def append_update_to_response(response, update, restore_state):
    """
    Adds the XML from the case_update to the restore response.
    If factor is > 1 it will append that many updates to the response for load testing purposes.
    """
    current_count = 0
    original_update = update
    while current_count < restore_state.loadtest_factor:
        element = get_case_element(update.case, update.required_updates, restore_state.version)
        response.append(element)
        current_count += 1
        if current_count < restore_state.loadtest_factor:
            update = transform_loadtest_update(original_update, current_count)
        #only add user case on the first iteration
        if original_update.case.type == USERCASE_TYPE:
            return
