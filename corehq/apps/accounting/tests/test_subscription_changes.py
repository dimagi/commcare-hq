from corehq.apps.domain.models import Domain
from django.test import SimpleTestCase
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import (
    Subscription, BillingAccount, DefaultProductPlan, SoftwarePlanEdition,
    Subscriber)
from corehq.apps.users.models import (
    Permissions, UserRole, UserRolePresets, WebUser, CommCareUser,
)


class TestSubscriptionEmailLogic(SimpleTestCase):

    def test_new_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=True), False)

    def test_non_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=False), True)

    def _run_test(self, old_sub, new_sub, expected_output):
        self.assertEqual(expected_output, Subscriber.should_send_subscription_notification(old_sub, new_sub))


class TestUserRoleSubscriptionChanges(BaseAccountingTest):
    min_subscription_length = 3

    def setUp(self):
        super(TestUserRoleSubscriptionChanges, self).setUp()
        self.domain = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.domain.save()
        UserRole.init_domain_with_presets(self.domain.name)
        self.user_roles = UserRole.by_domain(self.domain.name)
        self.custom_role = UserRole.get_or_create_with_permissions(
            self.domain.name,
            Permissions(edit_apps=True, edit_web_users=True),
            "Custom Role"
        )
        self.custom_role.save()
        self.read_only_role = UserRole.get_read_only_role_by_domain(self.domain.name)

        self.admin_user = generator.arbitrary_web_user()
        self.admin_user.add_domain_membership(self.domain.name, is_admin=True)
        self.admin_user.save()

        self.web_users = []
        self.commcare_users = []
        for role in [self.custom_role] + self.user_roles:
            web_user = generator.arbitrary_web_user()
            web_user.add_domain_membership(self.domain.name, role_id=role.get_id)
            web_user.save()
            self.web_users.append(web_user)

            commcare_user = generator.arbitrary_commcare_user(
                domain=self.domain.name)
            commcare_user.set_role(self.domain.name, role.get_qualified_id())
            commcare_user.save()
            self.commcare_users.append(commcare_user)

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,created_by=self.admin_user.username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.domain.name,edition=SoftwarePlanEdition.ADVANCED)

    def test_cancellation(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user.username
        )
        self._change_std_roles()
        subscription.cancel_subscription(web_user=self.admin_user.username)

        custom_role = UserRole.get(self.custom_role.get_id)
        self.assertTrue(custom_role.is_archived)

        # disable this part of the test until we improve the UX for notifying
        # downgraded users of their privilege changes
        # custom_web_user = WebUser.get(self.web_users[0].get_id)
        # custom_commcare_user = CommCareUser.get(self.commcare_users[0].get_id)
        # self.assertEqual(
        #     custom_web_user.get_domain_membership(self.domain.name).role_id,
        #     self.read_only_role.get_id
        # )
        # self.assertIsNone(
        #     custom_commcare_user.get_domain_membership(self.domain.name).role_id
        # )
        
        self._assertInitialRoles()
        self._assertStdUsers()

    def test_resubscription(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user.username
        )
        self._change_std_roles()
        subscription.cancel_subscription(web_user=self.admin_user.username)
        custom_role = UserRole.get(self.custom_role.get_id)
        self.assertTrue(custom_role.is_archived)
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user.username
        )
        custom_role = UserRole.get(self.custom_role.get_id)
        self.assertFalse(custom_role.is_archived)

        # disable this part of the test until we improve the UX for notifying
        # downgraded users of their privilege changes
        # custom_web_user = WebUser.get(self.web_users[0].get_id)
        # custom_commcare_user = CommCareUser.get(self.commcare_users[0].get_id)
        # self.assertEqual(
        #     custom_web_user.get_domain_membership(self.domain.name).role_id,
        #     self.read_only_role.get_id
        # )
        # self.assertIsNone(
        #     custom_commcare_user.get_domain_membership(self.domain.name).role_id
        # )

        self._assertInitialRoles()
        self._assertStdUsers()
        subscription.cancel_subscription(web_user=self.admin_user.username)

    def _change_std_roles(self):
        for u in self.user_roles:
            user_role = UserRole.get(u.get_id)
            user_role.permissions = Permissions(
                view_reports=True, edit_commcare_users=True, edit_apps=True,
                edit_data=True
            )
            user_role.save()

    def _assertInitialRoles(self):
        for u in self.user_roles:
            user_role = UserRole.get(u.get_id)
            self.assertEqual(
                user_role.permissions,
                UserRolePresets.get_permissions(user_role.name)
            )

    def _assertStdUsers(self):
        for ind, wu in enumerate(self.web_users[1:]):
            web_user = WebUser.get(wu.get_id)
            self.assertEqual(
                web_user.get_domain_membership(self.domain.name).role_id,
                self.user_roles[ind].get_id
            )

        for ind, cc in enumerate(self.commcare_users[1:]):
            commcare_user = CommCareUser.get(cc.get_id)
            self.assertEqual(
                commcare_user.get_domain_membership(self.domain.name).role_id,
                self.user_roles[ind].get_id
            )

    def tearDown(self):
        self.domain.delete()
        self.admin_user.delete()
        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
        super(TestUserRoleSubscriptionChanges, self).tearDown()
