from datetime import datetime, timedelta

from django_prbac.models import Role

from corehq.apps.accounting.models import (
    SoftwarePlanEdition,
    SoftwarePlan,
    SoftwarePlanVisibility,
    SoftwareProductRate,
    SoftwarePlanVersion,
    Subscription,
    BillingAccount,
)
from corehq.apps.accounting.tests import generator as accounting_gen
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.generator import generate_domain_subscription
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.util.test_utils import unit_testing_only


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


@unit_testing_only
def get_enterprise_account():
    billing_contact = accounting_gen.create_arbitrary_web_user_name()
    dimagi_user = accounting_gen.create_arbitrary_web_user_name(is_dimagi=True)
    return accounting_gen.billing_account(
        dimagi_user, billing_contact, is_customer_account=True
    )


@unit_testing_only
def get_enterprise_software_plan():
    enterprise_plan = SoftwarePlan.objects.create(
        name="Enterprise Plan",
        description="Enterprise Plan",
        edition=SoftwarePlanEdition.ENTERPRISE,
        visibility=SoftwarePlanVisibility.INTERNAL,
        is_customer_software_plan=True,
    )
    first_product_rate = SoftwareProductRate.objects.create(
        monthly_fee=3000,
        name="HQ Enterprise"
    )
    return SoftwarePlanVersion.objects.create(
        plan=enterprise_plan,
        role=Role.objects.first(),  # arbitrary role... does not matter
        product_rate=first_product_rate
    )


@unit_testing_only
def add_domains_to_enterprise_account(account, domains, plan_version, date_start):
    for domain in domains:
        generate_domain_subscription(
            account,
            domain,
            date_start,
            None,
            plan_version=plan_version,
            is_active=True,
        )
