from functools import wraps

from django.http import Http404

from corehq.apps.accounting.utils.account import (
    request_has_permissions_for_enterprise_admin,
    get_account_or_404,
)


def require_enterprise_admin(view_func):
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        if not hasattr(request, 'couch_user'):
            raise Http404()

        account = get_account_or_404(domain)
        if not request_has_permissions_for_enterprise_admin(request, account):
            # we want these urls to remain ambiguous/not discoverable so
            # raise 404 not 403
            raise Http404()
        request.account = account
        return view_func(request, domain, *args, **kwargs)
    return _inner
