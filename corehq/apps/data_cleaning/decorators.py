from functools import wraps

from no_exceptions.exceptions import Http403

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.privileges import BULK_DATA_EDITING


def require_bulk_data_cleaning_cases(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        if not bulk_data_cleaning_enabled_for_request(request):
            raise Http403

        return view_func(request, *args, **kwargs)

    return _inner


def bulk_data_cleaning_enabled_for_request(request):
    if domain_has_privilege(request.domain, BULK_DATA_EDITING):
        if hasattr(request, 'couch_user'):
            if request.couch_user.can_edit_data(request.domain):
                return True

    return False
