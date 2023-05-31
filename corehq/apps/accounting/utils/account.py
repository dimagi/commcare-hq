from django.http import Http404
from django_prbac.utils import has_privilege

from corehq import privileges
from corehq.apps.accounting.models import BillingAccount, Subscription, SoftwarePlanEdition


def get_account_or_404(domain):
    account = BillingAccount.get_account_by_domain(domain)
    if account is None:
        raise Http404()
    return account


def request_has_permissions_for_enterprise_admin(request, account):
    return (account.has_enterprise_admin(request.couch_user.username)
            or has_privilege(request, privileges.ACCOUNTING_ADMIN))


def is_user_restricted_from_domain_creation(couch_user):
    """
    :param couch_user: CouchUser
    :return: boolean indicating if user is restricted (True) or not (False)
    """
    domains = [dm.domain for dm in couch_user.domain_memberships]
    linked_accounts = list({BillingAccount.get_account_by_domain(d) for d in domains})
    if any([couch_user.username in acc.enterprise_admin_emails for acc in linked_accounts]):
        return True
    # if the user is part of any billing account that does not have this enabled
    # they can keep creating domains
    return all([acc.restrict_domain_creation for acc in linked_accounts])
