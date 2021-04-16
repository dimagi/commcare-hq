from functools import wraps

from corehq.apps.accounting.utils.subscription import get_account_or_404


def require_enterprise_admin(view_func):
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        # todo separate authorization from get method
        request.account = get_account_or_404(request, domain)
        return view_func(request, domain, *args, **kwargs)
    return _inner
