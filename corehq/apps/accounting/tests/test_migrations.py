import random
import uuid
from datetime import date, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
)
from corehq.apps.accounting.tasks import ensure_explicit_community_subscription
from corehq.apps.domain.models import Domain


class TestExplicitCommunitySubscriptions(TestCase):

    domain = None
    from_date = None

    @classmethod
    def setUpClass(cls):
        super(TestExplicitCommunitySubscriptions, cls).setUpClass()

        cls.domain = Domain(name=str(uuid.uuid4()))
        cls.domain.save()
        cls.from_date = date.today()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestExplicitCommunitySubscriptions, cls).tearDownClass()

    def test_no_preexisting_subscription(self):
        self._assign_community_subscriptions()

        self.assertEqual(Subscription.visible_objects.count(), 1)
        subscription = Subscription.visible_objects.all()[0]
        self.assertEqual(subscription.subscriber.domain, self.domain.name)
        self.assertEqual(subscription.date_start, self.from_date)
        self.assertIsNone(subscription.date_end)
        self.assertEqual(subscription.plan_version, self._most_recently_created_community_plan_version)
        self.assertTrue(subscription.skip_invoicing_if_no_feature_charges)

    def test_preexisting_current_subscription(self):
        preexisting_subscription = Subscription.new_domain_subscription(
            self._preexisting_subscription_account,
            self.domain.name,
            self._random_plan_version,
        )

        self._assign_community_subscriptions()

        self.assertEqual(Subscription.visible_objects.count(), 1)
        self.assertFalse(Subscription.visible_objects.exclude(subscriber__domain=self.domain.name).exists())
        self.assertEqual(Subscription.visible_objects.all()[0], preexisting_subscription)

    def test_preexisting_future_subscription(self):
        future_subscription_start_date = self.from_date + timedelta(days=10)
        plan_version = self._random_plan_version
        Subscription.new_domain_subscription(
            self._preexisting_subscription_account,
            self.domain.name,
            plan_version,
            date_start=future_subscription_start_date,
        )

        self._assign_community_subscriptions()

        self.assertEqual(Subscription.visible_objects.count(), 2)
        self.assertFalse(Subscription.visible_objects.exclude(subscriber__domain=self.domain.name).exists())
        self.assertIsNotNone(Subscription.visible_objects.get(
            date_start=self.from_date,
            date_end=future_subscription_start_date,
            plan_version=self._most_recently_created_community_plan_version,
            skip_invoicing_if_no_feature_charges=True,
        ))
        self.assertIsNotNone(Subscription.visible_objects.get(
            date_start=future_subscription_start_date,
            plan_version=plan_version,
        ))

    def test_preexisting_past_subscription(self):
        past_subscription_end_date = self.from_date - timedelta(days=10)
        past_subscription_start_date = past_subscription_end_date - timedelta(days=5)
        plan_version = self._random_plan_version
        Subscription.new_domain_subscription(
            self._preexisting_subscription_account,
            self.domain.name,
            plan_version,
            date_start=past_subscription_start_date,
            date_end=past_subscription_end_date,
        )

        self._assign_community_subscriptions()

        self.assertEqual(Subscription.visible_objects.count(), 2)
        self.assertFalse(Subscription.visible_objects.exclude(subscriber__domain=self.domain.name).exists())
        self.assertIsNotNone(Subscription.visible_objects.get(
            date_start=self.from_date,
            date_end=None,
            plan_version=self._most_recently_created_community_plan_version,
            skip_invoicing_if_no_feature_charges=True,
        ))
        self.assertIsNotNone(Subscription.visible_objects.get(
            date_start=past_subscription_start_date,
            date_end=past_subscription_end_date,
            plan_version=plan_version,
        ))

    def _assign_community_subscriptions(self):
        ensure_explicit_community_subscription(
            self.domain.name, self.from_date, SubscriptionAdjustmentMethod.DEFAULT_COMMUNITY
        )

    @property
    def _most_recently_created_community_plan_version(self):
        return DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.COMMUNITY)

    @property
    def _random_plan_version(self):
        return DefaultProductPlan.get_default_plan_version(
            edition=random.choice(SoftwarePlanEdition.SELF_SERVICE_ORDER + [SoftwarePlanEdition.ENTERPRISE]),
        )

    @property
    def _preexisting_subscription_account(self):
        return BillingAccount.get_or_create_account_by_domain(self.domain.name, created_by=self.domain.name)[0]
