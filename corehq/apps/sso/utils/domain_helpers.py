from corehq.apps.accounting.models import BillingAccount
from corehq.apps.sso.models import IdentityProvider


def domain_has_editable_identity_provider(domain):
    """
    Checks to see if an editable Identity Provider exists for a given domain name
    :param domain: string
    :return: boolean, True if editable Identity Provider exists.
    """
    owner = BillingAccount.get_account_by_domain(domain)
    return IdentityProvider.objects.filter(owner=owner, is_editable=True).exists()
