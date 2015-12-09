import datetime

from django.test.testcases import TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    Subscription,
    SubscriptionAdjustment,
    SoftwarePlanEdition,
    ProBonoStatus,
    SubscriptionType
)
from corehq.apps.analytics.signals import _get_subscription_properties_by_user
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.accounting import generator


class TestSubscriptionProperties(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_domain = Domain(name="base", is_active=True)
        cls.base_domain.save()
        cls.user = WebUser.create(cls.base_domain.name, "tarso", "*****")
        cls.user.save()

        cls._to_delete = []
        cls.community = Domain(name="community", is_active=True)
        cls.community.save()
        cls._setup_subscription(cls.community.name, SoftwarePlanEdition.COMMUNITY)

        cls.enterprise = Domain(name="enterprise", is_active=True)
        cls.enterprise.save()
        cls._setup_subscription(cls.enterprise.name, SoftwarePlanEdition.ENTERPRISE)

        for domain in [cls.community, cls.enterprise]:
            cls.user.add_domain_membership(domain.name, is_admin=True)

    @classmethod
    def _setup_subscription(cls, domain_name, software_plan):
        generator.instantiate_accounting_for_tests()

        plan = DefaultProductPlan.get_default_plan_by_domain(
            domain_name, edition=software_plan
        )
        account = BillingAccount.get_or_create_account_by_domain(
            domain_name, created_by="automated-test" + cls.__name__
        )[0]
        subscription = Subscription.new_domain_subscription(
            account,
            domain_name,
            plan,
            date_start=datetime.date.today() + datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5))
        subscription.is_active = True
        subscription.save()
        cls._to_delete.append(account)
        cls._to_delete.append(subscription)

    @classmethod
    def tesrDownClass(cls):
        SubscriptionAdjustment.objects.all().delete()
        for obj in [cls.base_domain, cls.community, cls.enterprise] + cls._to_delete:
            obj.delete()
        cls.user.delete()

    def test_properties(self):
        properties = _get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['is_on_community_plan'], 'yes')
        self.assertEqual(properties['is_on_standard_plan'], 'no')
        self.assertEqual(properties['is_on_advanced_plan'], 'no')
        self.assertEqual(properties['is_on_pro_plan'], 'no')
        self.assertEqual(properties['is_on_enterprise_plan'], 'yes')
        self.assertEqual(properties['max_edition_of_paying_plan'], SoftwarePlanEdition.ENTERPRISE)

    def test_probono_properties(self):
        properties = _get_subscription_properties_by_user(self.user)

        self.assertEqual(properties['is_on_pro_bono_plan'], 'no')
        self._change_to_probono(self.community.name, ProBonoStatus.YES)
        properties = _get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['is_on_pro_bono_plan'], 'yes')

        self.assertEqual(properties['is_on_discounted_plan'], 'no')
        self._change_to_probono(self.community.name, ProBonoStatus.DISCOUNTED)
        properties = _get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['is_on_discounted_plan'], 'yes')

    def test_extended_trial(self):
        properties = _get_subscription_properties_by_user(self.user)

        self.assertEqual(properties['is_on_extended_trial_plan'], 'no')
        self._change_to_extended_trial(self.community.name)
        properties = _get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['is_on_extended_trial_plan'], 'yes')

    def _change_to_probono(self, domain_name, pro_bono_status):
        plan, subscription = Subscription.get_subscribed_plan_by_domain(domain_name)
        subscription.update_subscription(
            pro_bono_status=pro_bono_status,
            date_start=datetime.date.today() + datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5)
        )

    def _change_to_extended_trial(self, domain_name):
        plan, subscription = Subscription.get_subscribed_plan_by_domain(domain_name)
        subscription.update_subscription(
            service_type=SubscriptionType.EXTENDED_TRIAL,
            date_start=datetime.date.today() + datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5)
        )
