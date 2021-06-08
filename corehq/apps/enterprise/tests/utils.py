from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tests import generator


def create_enterprise_permissions(email, source_domain, control_domains=None, ignore_domains=None):
    account = generator.billing_account(email, email)
    plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ENTERPRISE)
    subscriptions = []

    domains = [source_domain]
    if control_domains:
        domains.extend(control_domains)
    if ignore_domains:
        domains.extend(ignore_domains)
    for domain in domains:
        subscriptions.append(Subscription.new_domain_subscription(account, domain, plan))

    account.permissions_source_domain = source_domain
    account.permissions_ignore_domains = ignore_domains
    account.save()
