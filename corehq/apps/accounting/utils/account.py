from django.http import Http404
from django_prbac.utils import has_privilege

from corehq import privileges
from corehq.apps.accounting.models import BillingAccount


def get_account_or_404(domain):
    account = BillingAccount.get_account_by_domain(domain)
    if account is None:
        raise Http404()
    return account


def request_has_permissions_for_enterprise_admin(request, account):
    return (account.has_enterprise_admin(request.couch_user.username)
            or has_privilege(request, privileges.ACCOUNTING_ADMIN))
