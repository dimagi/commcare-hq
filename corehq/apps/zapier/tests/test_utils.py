from collections import namedtuple

from django.core.management import call_command

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import HQApiKey, WebUser

ZapierDomainConfig = namedtuple('ZapierDomainConfig', 'domain web_user api_key')


def bootstrap_domain_for_zapier(domain_name):
    domain_object = Domain.get_or_create_with_name(domain_name, is_active=True)

    _ensure_plans()
    account = BillingAccount.get_or_create_account_by_domain(domain_name, created_by="automated-test")[0]
    plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.PRO)
    subscription = Subscription.new_domain_subscription(account, domain_name, plan)
    subscription.is_active = True
    subscription.save()

    web_user = WebUser.create(domain_name, 'test', '******', None, None)
    api_key_object, _ = HQApiKey.objects.get_or_create(user=web_user.get_django_user())
    return ZapierDomainConfig(domain_object, web_user, api_key_object.plaintext_key)


def _ensure_plans():
    """Ensure PRBAC roles and accounting plans exist.

    In CI with --no-migrations, PRBAC roles and test plans are not
    created automatically. Bootstrap them if they don't already exist.
    """
    from corehq.apps.accounting.exceptions import AccountingError
    from corehq.apps.accounting.tests.generator import (
        bootstrap_test_software_plan_versions,
    )
    try:
        DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.PRO,
        )
    except AccountingError:
        call_command('cchq_prbac_bootstrap')
        bootstrap_test_software_plan_versions()
