from corehq.apps.accounting.models import BillingAccount
from corehq.apps.sso.models import IdentityProvider, TrustedIdentityProvider


def is_domain_using_sso(domain):
    """
    Determines whether a given project is under an active Identity Provider or
    if it trusts an active Identity Provider.
    :param domain: domain name (string)
    :return: boolean (True if using SSO based on the criteria above)
    """
    account = BillingAccount.get_account_by_domain(domain)
    return (
        IdentityProvider.objects.filter(owner=account, is_active=True).exists()
        or TrustedIdentityProvider.objects.filter(
            domain=domain,
            identity_provider__is_active=True
        ).exists()
    )
