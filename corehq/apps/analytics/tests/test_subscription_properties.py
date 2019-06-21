from __future__ import absolute_import
from __future__ import unicode_literals
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
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.analytics.tasks import get_subscription_properties_by_user
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class TestSubscriptionProperties(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestSubscriptionProperties, cls).setUpClass()

        cls.base_domain = Domain(name="base", is_active=True)
        cls.base_domain.save()
        cls.user = WebUser.create(cls.base_domain.name, "tarso", "*****")
        cls.user.save()

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
        plan = DefaultProductPlan.get_default_plan_version(edition=software_plan)
        account = BillingAccount.get_or_create_account_by_domain(
            domain_name, created_by="automated-test" + cls.__name__
        )[0]
        subscription = Subscription.new_domain_subscription(
            account,
            domain_name,
            plan,
            date_start=datetime.date.today() - datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5))
        subscription.save()

    @classmethod
    def tearDownClass(cls):
        cls.base_domain.delete()
        cls.user.delete()
        clear_plan_version_cache()
        super(TestSubscriptionProperties, cls).tearDownClass()

    def test_properties(self):
        properties = get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['_is_on_community_plan'], 'yes')
        self.assertEqual(properties['_is_on_standard_plan'], 'no')
        self.assertEqual(properties['_is_on_pro_plan'], 'no')
        self.assertEqual(properties['_max_edition_of_paying_plan'], SoftwarePlanEdition.ENTERPRISE)

    def test_probono_properties(self):
        properties = get_subscription_properties_by_user(self.user)

        self.assertEqual(properties['_is_on_pro_bono_plan'], 'no')
        self._change_to_probono(self.community.name, ProBonoStatus.YES)
        properties = get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['_is_on_pro_bono_plan'], 'yes')

        self.assertEqual(properties['_is_on_discounted_plan'], 'no')
        self._change_to_probono(self.community.name, ProBonoStatus.DISCOUNTED)
        properties = get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['_is_on_discounted_plan'], 'yes')

    def test_extended_trial(self):
        properties = get_subscription_properties_by_user(self.user)

        self.assertEqual(properties['_is_on_extended_trial_plan'], 'no')
        self._change_to_extended_trial(self.community.name)
        properties = get_subscription_properties_by_user(self.user)
        self.assertEqual(properties['_is_on_extended_trial_plan'], 'yes')

    def _change_to_probono(self, domain_name, pro_bono_status):
        subscription = Subscription.get_active_subscription_by_domain(domain_name)
        subscription.update_subscription(
            pro_bono_status=pro_bono_status,
            date_start=datetime.date.today() - datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5)
        )

    def _change_to_extended_trial(self, domain_name):
        subscription = Subscription.get_active_subscription_by_domain(domain_name)
        subscription.update_subscription(
            service_type=SubscriptionType.EXTENDED_TRIAL,
            date_start=datetime.date.today() - datetime.timedelta(days=1),
            date_end=datetime.date.today() + datetime.timedelta(days=5)
        )
