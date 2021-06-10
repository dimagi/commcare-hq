from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.enterprise.models import EnterprisePermissions


def create_enterprise_permissions(email, source_domain, domains=None, other_domains=None):
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
        is_enabled=True,
        source_domain=source_domain,
        domains=domains,
    ).save()
