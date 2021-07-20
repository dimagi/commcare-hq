from datetime import date, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.dbaccessors import get_available_domains_to_link
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestGetAvailableDomainsToLink(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestGetAvailableDomainsToLink, cls).setUpClass()

        # Setup non-enterprise subscription
        cls.non_enterprise_domain_obj_1 = create_domain('non-enterprise-1')
        cls.non_enterprise_domain_obj_2 = create_domain('non-enterprise-2')
        cls.non_enterprise_account, _ = BillingAccount.get_or_create_account_by_domain(
            cls.non_enterprise_domain_obj_1.name,
            created_by='user@test.com'
        )
        cls.non_enterprise_account.save()
        cls._add_domain_to_account(cls.non_enterprise_domain_obj_1.name,
                                   cls.non_enterprise_account,
                                   SoftwarePlanEdition.COMMUNITY)
        cls._add_domain_to_account(cls.non_enterprise_domain_obj_2.name,
                                   cls.non_enterprise_account,
                                   SoftwarePlanEdition.COMMUNITY)

        # Setup enterprise subscription
        cls.enterprise_domain_obj_1 = create_domain('enterprise-1')
        cls.enterprise_domain_obj_2 = create_domain('enterprise-2')
        cls.enterprise_account, _ = BillingAccount.get_or_create_account_by_domain(
            cls.enterprise_domain_obj_1.name,
            created_by='user@test.com'
        )
        cls.enterprise_account.save()
        cls._add_domain_to_account(cls.enterprise_domain_obj_1.name,
                                   cls.enterprise_account,
                                   SoftwarePlanEdition.ENTERPRISE)

        cls._add_domain_to_account(cls.enterprise_domain_obj_2.name,
                                   cls.enterprise_account,
                                   SoftwarePlanEdition.ENTERPRISE)

        cls.user = WebUser.create(
            domain=cls.enterprise_domain_obj_1.name,
            username='user@enterprise.com',
            password='***',
            created_by=None,
            created_via=None,
        )
        cls.user.delete_domain_membership(cls.enterprise_domain_obj_1.name)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.enterprise_domain_obj_1.name, deleted_by=None)
        cls.non_enterprise_domain_obj_1.delete()
        cls.non_enterprise_domain_obj_2.delete()
        cls.enterprise_domain_obj_1.delete()
        cls.enterprise_domain_obj_2.delete()
        SubscriptionAdjustment.objects.all().delete()
        Subscription.visible_and_suppressed_objects.all().delete()
        cls.non_enterprise_account.delete()
        cls.enterprise_account.delete()
        super(TestGetAvailableDomainsToLink, cls).tearDownClass()

    def test_non_enterprise_account_returns_empty_list(self):
        self.user.add_domain_membership(self.non_enterprise_domain_obj_1.name)
        self.user.set_role(self.non_enterprise_domain_obj_1.name, 'admin')
        self.user.add_domain_membership(self.non_enterprise_domain_obj_2.name)
        self.user.set_role(self.non_enterprise_domain_obj_2.name, 'admin')
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_2.name)

        available_domains = get_available_domains_to_link(self.non_enterprise_domain_obj_1.name, self.user)
        self.assertEqual([], available_domains)

    @flag_enabled("LINKED_DOMAINS")
    def test_non_enterprise_account_with_feature_flag_returns_some(self):
        self.user.add_domain_membership(self.non_enterprise_domain_obj_1.name)
        self.user.add_domain_membership(self.non_enterprise_domain_obj_2.name)
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_2.name)

        available_domains = get_available_domains_to_link(self.non_enterprise_domain_obj_1.name, self.user)
        self.assertEqual(1, len(available_domains))
        self.assertEqual(self.non_enterprise_domain_obj_2.name, available_domains[0])

    def test_enterprise_account_with_admin_user_returns_some(self):
        self.user.add_domain_membership(self.enterprise_domain_obj_1.name)
        self.user.set_role(self.enterprise_domain_obj_1.name, 'admin')
        self.user.add_domain_membership(self.enterprise_domain_obj_2.name)
        self.user.set_role(self.enterprise_domain_obj_2.name, 'admin')
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_2.name)

        available_domains = get_available_domains_to_link(self.enterprise_domain_obj_1.name, self.user)
        self.assertEqual(1, len(available_domains))
        self.assertEqual(self.enterprise_domain_obj_2.name, available_domains[0])

    def test_enterprise_account_without_admin_user_returns_empty_list(self):
        self.user.add_domain_membership(self.enterprise_domain_obj_1.name)
        self.user.add_domain_membership(self.enterprise_domain_obj_2.name)
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_2.name)

        available_domains = get_available_domains_to_link(self.enterprise_domain_obj_1.name, self.user)
        self.assertEqual([], available_domains)

    def test_enterprise_account_with_admin_user_in_upstream_returns_empty_list(self):
        self.user.add_domain_membership(self.enterprise_domain_obj_1.name)
        self.user.set_role(self.enterprise_domain_obj_1.name, 'admin')
        self.user.add_domain_membership(self.enterprise_domain_obj_2.name, is_admin=False)
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_2.name)

        available_domains = get_available_domains_to_link(self.enterprise_domain_obj_1.name, self.user)
        self.assertEqual([], available_domains)

    def test_enterprise_account_with_linked_domains_returns_empty_list(self):
        self.user.add_domain_membership(self.enterprise_domain_obj_1.name)
        self.user.set_role(self.enterprise_domain_obj_1.name, 'admin')
        self.user.add_domain_membership(self.enterprise_domain_obj_2.name)
        self.user.set_role(self.enterprise_domain_obj_2.name, 'admin')
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.enterprise_domain_obj_2.name)

        link = DomainLink.link_domains(self.enterprise_domain_obj_2.name, self.enterprise_domain_obj_1.name)
        self.addCleanup(link.delete)

        available_domains = get_available_domains_to_link(self.enterprise_domain_obj_2.name, self.user)
        self.assertEqual([], available_domains)

    @flag_enabled("LINKED_DOMAINS")
    def test_non_enterprise_account_with_linked_domains_returns_empty_list(self):
        self.user.add_domain_membership(self.non_enterprise_domain_obj_1.name)
        self.user.set_role(self.non_enterprise_domain_obj_1.name, 'admin')
        self.user.add_domain_membership(self.non_enterprise_domain_obj_2.name)
        self.user.set_role(self.non_enterprise_domain_obj_2.name, 'admin')
        self.user.save()
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_1.name)
        self.addCleanup(self.user.delete_domain_membership, domain=self.non_enterprise_domain_obj_2.name)

        link = DomainLink.link_domains(
            self.non_enterprise_domain_obj_2.name,
            self.non_enterprise_domain_obj_1.name
        )
        self.addCleanup(link.delete)

        available_domains = get_available_domains_to_link(self.non_enterprise_domain_obj_1.name, self.user)
        self.assertEqual([], available_domains)

    @classmethod
    def _add_domain_to_account(cls, domain_name, account, edition):
        subscription = Subscription.new_domain_subscription(
            account, domain_name,
            DefaultProductPlan.get_default_plan_version(edition=edition),
            date_start=date.today() - timedelta(days=3)
        )
        subscription.is_active = True
        subscription.save()
