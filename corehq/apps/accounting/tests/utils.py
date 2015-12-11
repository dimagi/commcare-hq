from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SubscriptionAdjustment, Subscription


class DomainSubscriptionMixin(object):
    """
    util for setting up a subscription for domain
    """

    @classmethod
    def setup_subscription(cls, domain_name, software_plan):
        generator.instantiate_accounting_for_tests()

        plan = DefaultProductPlan.get_default_plan_by_domain(
            domain_name, edition=software_plan
        )
        cls.account = BillingAccount.get_or_create_account_by_domain(
            domain_name, created_by="automated-test" + cls.__name__
        )[0]
        cls.subscription = Subscription.new_domain_subscription(cls.account, domain_name, plan)
        cls.subscription.is_active = True
        cls.subscription.save()

    @classmethod
    def teardown_subscription(cls):
        SubscriptionAdjustment.objects.all().delete()
        cls.subscription.delete()
        cls.account.delete()
