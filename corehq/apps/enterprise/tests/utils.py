from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.enterprise.models import EnterprisePermissions


def create_enterprise_permissions(email, source_domain, domains=None, other_domains=None):
    """
    Creates an account using the given email address and sets up enterprise permissions
    with the given source domain. Both `domains` and `other_domains` are added to the new account,
    but only `domains` are controlled by enterprise permissions.
    """
    account = generator.billing_account(email, email)
    plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ENTERPRISE)
    subscriptions = []

    all_domains = [source_domain]
    if domains:
        domains.extend(domains)
    if other_domains:
        domains.extend(other_domains)
    for domain in all_domains:
        subscriptions.append(Subscription.new_domain_subscription(account, domain, plan))

    EnterprisePermissions(
        account=account,
        is_enabled=True,
        source_domain=source_domain,
        domains=domains,
    ).save()
