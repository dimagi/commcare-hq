from copy import deepcopy
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.data_providers.case.utils import CaseSyncUpdate
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
        return '{}-{}'.format(id, count)
    case = CommCareCase.wrap(deepcopy(update.case._doc))
    case._id = _map_id(case._id, factor)
    for index in case.indices:
        index.referenced_id = _map_id(index.referenced_id, factor)
    case.name = '{} ({})'.format(case.name, factor)
    return CaseSyncUpdate(case, update.sync_token, required_updates=update.required_updates)

