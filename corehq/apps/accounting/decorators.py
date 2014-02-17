from django.http import Http404
from corehq import BillingAccountAdmin


def require_billing_admin():
    def decorate(fn):
        """
        Decorator to require the current logged in user to be a billing admin to access the decorated view.
        """
        def wrapped(request, *args, **kwargs):
            if not hasattr(request, 'couch_user') and not hasattr(request, 'domain'):
                raise Http404()
            is_billing_admin = BillingAccountAdmin.get_admin_status_and_account(request.couch_user, request.domain)[0]
            if not (is_billing_admin or request.couch_user.is_superuser):
                raise Http404()
            return fn(request, *args, **kwargs)

        return wrapped

    return decorate
