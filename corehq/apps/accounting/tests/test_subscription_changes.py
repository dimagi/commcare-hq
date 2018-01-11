from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from mock import patch, Mock

from corehq.apps.accounting.models import (
    Subscription, BillingAccount, DefaultProductPlan, SoftwarePlanEdition,
    Subscriber)
from corehq.apps.accounting.subscription_changes import DomainDowngradeActionHandler
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import (
    Permissions, UserRole, UserRolePresets, WebUser, CommCareUser,
)
from corehq.privileges import REPORT_BUILDER_ADD_ON_PRIVS


class TestSubscriptionEmailLogic(SimpleTestCase):

    def test_new_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=True), False)

    def test_non_trial_with_no_previous(self):
        self._run_test(None, Subscription(is_trial=False), False)

    def test_non_trial_with_previous(self):
        self._run_test(Subscription(is_trial=False), Subscription(is_trial=False), True)
        self._run_test(Subscription(is_trial=True), Subscription(is_trial=False), True)

    def _run_test(self, old_sub, new_sub, expected_output):
        self.assertEqual(expected_output, Subscriber.should_send_subscription_notification(old_sub, new_sub))


class TestUserRoleSubscriptionChanges(BaseAccountingTest):

    def setUp(self):
        super(TestUserRoleSubscriptionChanges, self).setUp()
        self.domain = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.domain.save()
        self.other_domain = Domain(
            name="other-domain",
            is_active=True,
        )
        self.other_domain.save()
        UserRole.init_domain_with_presets(self.domain.name)
        self.user_roles = UserRole.by_domain(self.domain.name)
        self.custom_role = UserRole.get_or_create_with_permissions(
            self.domain.name,
            Permissions(edit_apps=True, edit_web_users=True),
            "Custom Role"
        )
        self.custom_role.save()
        self.read_only_role = UserRole.get_read_only_role_by_domain(self.domain.name)

        self.admin_username = generator.create_arbitrary_web_user_name()

        self.web_users = []
        self.commcare_users = []
        for role in [self.custom_role] + self.user_roles:
            web_user = WebUser.create(
                self.other_domain.name, generator.create_arbitrary_web_user_name(), 'test123'
            )
            web_user.is_active = True
            web_user.add_domain_membership(self.domain.name, role_id=role.get_id)
            web_user.save()
            self.web_users.append(web_user)

            commcare_user = generator.arbitrary_commcare_user(
                domain=self.domain.name)
            commcare_user.set_role(self.domain.name, role.get_qualified_id())
            commcare_user.save()
            self.commcare_users.append(commcare_user)

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)

    def test_cancellation(self):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_username
        )
        self._change_std_roles()
        subscription.change_plan(DefaultProductPlan.get_default_plan_version())

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
            web_user=self.admin_username
        )
        self._change_std_roles()
        new_subscription = subscription.change_plan(DefaultProductPlan.get_default_plan_version())
        custom_role = UserRole.get(self.custom_role.get_id)
        self.assertTrue(custom_role.is_archived)
        new_subscription.change_plan(self.advanced_plan, web_user=self.admin_username)
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

    def _change_std_roles(self):
        for u in self.user_roles:
            user_role = UserRole.get(u.get_id)
            user_role.permissions = Permissions(
                view_reports=True, edit_commcare_users=True, edit_locations=True,
                edit_apps=True, edit_data=True
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
        self.other_domain.delete()
        super(TestUserRoleSubscriptionChanges, self).tearDown()


class TestSubscriptionChangeResourceConflict(BaseAccountingTest):

    def setUp(self):
        self.domain_name = 'test-domain-changes'
        self.domain = Domain(
            name=self.domain_name,
            is_active=True,
            description='spam',
        )
        self.domain.save()

    def tearDown(self):
        self.domain.delete()
        super(TestSubscriptionChangeResourceConflict, self).tearDown()

    def test_domain_changes(self):
        role = Mock()
        role.memberships_granted.all.return_value = []
        version = Mock()
        version.role.get_cached_role.return_value = role
        handler = DomainDowngradeActionHandler(
            self.domain, new_plan_version=version, changed_privs=REPORT_BUILDER_ADD_ON_PRIVS
        )

        conflicting_domain = Domain.get_by_name(self.domain_name)
        conflicting_domain.description = 'eggs'
        conflicting_domain.save()

        get_by_name_func = Domain.get_by_name
        with patch('corehq.apps.accounting.subscription_changes.Domain') as Domain_patch:
            Domain_patch.get_by_name.side_effect = lambda name: get_by_name_func(name)
            handler.get_response()
            Domain_patch.get_by_name.assert_called_with(self.domain_name)
