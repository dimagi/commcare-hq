from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SubscriptionAdjustment, Subscription
from corehq.apps.accounting.tests import generator


class DomainSubscriptionMixin(object):
    """
    util for setting up a subscription for domain
    """

    @classmethod
    def setup_subscription(cls, domain_name, software_plan):
        generator.bootstrap_test_software_plan_versions()

        plan = DefaultProductPlan.get_default_plan_version(edition=software_plan)
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
