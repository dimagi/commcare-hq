from collections import namedtuple


from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import HQApiKey, WebUser

ZapierDomainConfig = namedtuple('ZapierDomainConfig', 'domain web_user api_key')


def bootrap_domain_for_zapier(domain_name):
    domain_object = Domain.get_or_create_with_name(domain_name, is_active=True)

    account = BillingAccount.get_or_create_account_by_domain(domain_name, created_by="automated-test")[0]
    plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)
    subscription = Subscription.new_domain_subscription(account, domain_name, plan)
    subscription.is_active = True
    subscription.save()

    web_user = WebUser.create(domain_name, 'test', '******', None, None)
    api_key_object, _ = HQApiKey.objects.get_or_create(user=web_user.get_django_user())
    return ZapierDomainConfig(domain_object, web_user, api_key_object.plaintext_key)
