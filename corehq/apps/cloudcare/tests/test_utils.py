from django.test import TestCase

from corehq.apps.app_manager.models import (
    Application,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.cloudcare.models import ApplicationAccess, SQLAppGroup
from corehq.apps.cloudcare.utils import (
    can_user_access_web_app,
    get_mobile_ucr_count,
    should_restrict_web_apps_usage,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import flag_disabled, flag_enabled


class TestShouldRestrictWebAppsUsage(TestCase):

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_is_under_limit_and_neither_toggle_is_enable(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 0)
        self.assertFalse(result)

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_neither_toggle_is_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 2)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_ALLOW_WEB_APPS_RESTRICTION_is_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 2)
        self.assertFalse(result)

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_exceeds_limit_and_MOBILE_UCR_is_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 2)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_is_under_limit_and_both_flags_are_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=2):
            result = should_restrict_web_apps_usage(self.domain, 1)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_false_if_domain_ucr_count_equals_limit_and_both_flags_are_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 1)
        self.assertFalse(result)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_true_if_domain_ucr_count_exceeds_limit_and_both_flags_are_enabled(self):
        with self.settings(MAX_MOBILE_UCR_LIMIT=1):
            result = should_restrict_web_apps_usage(self.domain, 2)
        self.assertTrue(result)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'restrict-web-apps-test'


class TestGetMobileUCRCount(TestCase):

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_zero_if_neither_toggle_is_enable(self):
        self._create_app_with_reports(report_count=1)
        count = get_mobile_ucr_count(self.domain.name)
        self.assertEqual(count, 0)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_disabled("MOBILE_UCR")
    def test_returns_zero_if_ALLOW_WEB_APPS_RESTRICTION_is_enabled(self):
        self._create_app_with_reports(report_count=1)
        count = get_mobile_ucr_count(self.domain.name)
        self.assertEqual(count, 0)

    @flag_disabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_zero_if_MOBILE_UCR_is_enabled(self):
        self._create_app_with_reports(report_count=1)
        count = get_mobile_ucr_count(self.domain.name)
        self.assertEqual(count, 0)

    @flag_enabled("ALLOW_WEB_APPS_RESTRICTION")
    @flag_enabled("MOBILE_UCR")
    def test_returns_ucr_count_if_both_flags_are_enabled(self):
        self._create_app_with_reports(report_count=1)
        count = get_mobile_ucr_count(self.domain.name)
        self.assertEqual(count, 1)

    def _create_app_with_reports(self, report_count=1):
        configs = []
        for idx in range(report_count):
            configs.append(ReportAppConfig(report_id=f'{idx}'))
        report_module = ReportModule(name={"test": "Reports"}, report_configs=configs)
        self.app = Application(domain=self.domain.name, version=1, modules=[report_module])
        self.app.save()
        self.addCleanup(self.app.delete)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('mobile-ucr-count-test')
        cls.addClassCleanup(cls.domain.delete)


class TestCanUserAccessWebApp(TestCase):

    def test_commcare_user_has_access_if_assigned_role_that_can_access_all_web_apps(self):
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(access_web_apps=True))

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    def test_commcare_user_has_access_if_assigned_role_that_cannot_access_web_apps(self):
        # mobile users have not historically required this new permission, so we need to assume they have access
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(access_web_apps=False))

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    def test_commcare_user_has_access_if_assigned_role_that_can_access_specific_app(self):
        self.set_role_on_user_with_permissions(
            self.commcare_user, HqPermissions(web_apps_list=[self.build_doc["copy_of"]])
        )

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    def test_commcare_user_does_not_have_access_if_assigned_role_that_can_access_different_app(self):
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(web_apps_list=["random-app"]))

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertFalse(has_access)

    def test_web_user_has_access_if_assigned_role_that_can_access_all_web_apps(self):
        self.set_role_on_user_with_permissions(self.web_user, HqPermissions(access_web_apps=True))

        has_access = can_user_access_web_app(self.web_user, self.build_doc)

        self.assertTrue(has_access)

    def test_web_user_does_not_have_access_if_assigned_role_that_cannot_access_web_apps(self):
        self.set_role_on_user_with_permissions(self.web_user, HqPermissions(access_web_apps=False))

        has_access = can_user_access_web_app(self.web_user, self.build_doc)

        self.assertFalse(has_access)

    def test_web_user_has_access_if_assigned_role_that_can_access_specific_app(self):
        self.set_role_on_user_with_permissions(
            self.web_user, HqPermissions(web_apps_list=[self.build_doc["copy_of"]])
        )

        has_access = can_user_access_web_app(self.web_user, self.build_doc)

        self.assertTrue(has_access)

    def test_web_user_has_access_to_canonical_if_assigned_role_that_can_access_specific_app(self):
        self.set_role_on_user_with_permissions(
            self.web_user, HqPermissions(web_apps_list=[self.build_doc["copy_of"]])
        )

        has_access = can_user_access_web_app(self.web_user, self.app_doc)

        self.assertTrue(has_access)

    def test_web_user_does_not_have_access_if_assigned_role_that_can_access_different_app(self):
        self.set_role_on_user_with_permissions(self.web_user, HqPermissions(web_apps_list=["random-app"]))

        has_access = can_user_access_web_app(self.web_user, self.build_doc)

        self.assertFalse(has_access)

    def test_web_user_does_not_have_access_to_canonical_if_assigned_role_that_can_access_different_app(self):
        self.set_role_on_user_with_permissions(self.web_user, HqPermissions(web_apps_list=["random-app"]))

        has_access = can_user_access_web_app(self.web_user, self.app_doc)

        self.assertFalse(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_commcare_user_has_access_if_assigned_role_that_cannot_access_web_apps_and_in_group_with_access_to_specific_app(self):  # noqa: E501
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(access_web_apps=False))
        self.add_user_to_group_for_app_id(self.commcare_user, self.build_doc['_id'])

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_commcare_user_does_not_have_access_if_assigned_role_that_can_access_different_app_and_in_group_with_access_to_specific_app(self):  # noqa: E501
        # this tests the precendence of permissions over groups
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(web_apps_list=["random-app"]))
        self.add_user_to_group_for_app_id(self.commcare_user, self.build_doc['_id'])

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertFalse(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_commcare_user_does_not_have_access_if_assigned_role_that_can_access_different_app_and_in_group_with_access_to_different_app(self):  # noqa: E501
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(web_apps_list=["random-app"]))
        self.add_user_to_group_for_app_id(self.commcare_user, 'random-app')

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertFalse(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_commcare_user_has_access_if_assigned_role_that_can_access_specific_app_and_in_group_with_access_to_specific_app(self):  # noqa: E501
        self.set_role_on_user_with_permissions(
            self.commcare_user, HqPermissions(web_apps_list=[self.build_doc["copy_of"]])
        )
        self.add_user_to_group_for_app_id(self.commcare_user, self.build_doc['_id'])

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_commcare_user_has_access_if_assigned_role_that_can_access_specific_app_and_in_group_with_access_to_different_app(self):  # noqa: E501
        self.set_role_on_user_with_permissions(
            self.commcare_user, HqPermissions(web_apps_list=[self.build_doc["copy_of"]])
        )
        self.add_user_to_group_for_app_id(self.commcare_user, "random-app")

        has_access = can_user_access_web_app(self.commcare_user, self.build_doc)

        self.assertTrue(has_access)

    @flag_enabled("WEB_APPS_PERMISSIONS_VIA_GROUPS")
    def test_permission_takes_precedence_over_group_for_web_user(self):
        # web users always have permission via groups
        self.set_role_on_user_with_permissions(self.commcare_user, HqPermissions(web_apps_list=["random-app"]))

        has_access = can_user_access_web_app(self.web_user, self.build_doc)

        self.assertFalse(has_access)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-user-access-to-web-apps'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def setUp(self):
        super().setUp()
        self.app_doc = {'doc_type': 'Application', '_id': 'def456', 'copy_of': None, 'domain': self.domain}
        self.build_doc = {
            **self.app_doc,
            'copy_of': self.app_doc['_id'],
            '_id': 'abc123',
        }
        self.commcare_user = CommCareUser.create(self.domain, 'bob@test.commcarehq.org', 'password', None, None)
        self.addCleanup(self.commcare_user.delete, None, None)
        self.web_user = WebUser.create(self.domain, 'bob@test.com', 'password', None, None)
        self.addCleanup(self.web_user.delete, None, None)

    def set_role_on_user_with_permissions(self, user, permissions):
        role = UserRole.create(self.domain, name='test-role', permissions=permissions)
        user.set_role(self.domain, role.get_qualified_id())

    def add_user_to_group_for_app_id(self, user, app_id):
        group = Group(domain=self.domain)
        group.add_user(user._id)
        group.save()
        self.addCleanup(group.delete)
        app_access = ApplicationAccess.objects.create(domain=self.domain, restrict=True)
        SQLAppGroup.objects.create(app_id=app_id, group_id=group._id, application_access=app_access)
