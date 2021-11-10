from datetime import datetime, timedelta

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests import generator
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.models import EnterprisePermissions


def create_enterprise_permissions(email, source_domain, domains=None, other_domains=None):
    """
    Creates an account using the given email address and sets up enterprise permissions
    with the given source domain. Both `domains` and `other_domains` are added to the new account,
    but only `domains` are controlled by enterprise permissions.

    All given domains must exist.
    """
    account = generator.billing_account(email, email, is_customer_account=True)
    plan_version = generator.subscribable_plan_version(edition=SoftwarePlanEdition.ENTERPRISE)
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=365)
    subscriptions = []

    all_domains = [source_domain]
    if domains:
        all_domains.extend(domains)
    if other_domains:
        all_domains.extend(other_domains)
    for domain in all_domains:
        subscriptions.append(generator.generate_domain_subscription(
            account,
            Domain.get_by_name(domain),
            date_start=start_date,
            date_end=end_date,
            plan_version=plan_version,
            is_active=True,
        ))

    EnterprisePermissions(
        account=account,
        is_enabled=True,
        source_domain=source_domain,
        domains=domains,
    ).save()
