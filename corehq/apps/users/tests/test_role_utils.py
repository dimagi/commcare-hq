from django.test import TestCase

from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.apps.users.role_utils import (
    UserRolePresets,
    archive_custom_roles_for_domain,
    get_custom_roles_for_domain,
    initialize_domain_with_default_roles,
    reset_initial_roles_for_domain,
    unarchive_roles_for_domain,
    enable_attendance_coordinator_role_for_domain,
    archive_attendance_coordinator_role_for_domain,
    get_commcare_analytics_roles_by_user_domains,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.permissions import (
    COMMCARE_ANALYTICS_USER_PERMISSIONS,
    COMMCARE_ANALYTICS_GAMMA,
    COMMCARE_ANALYTICS_SQL_LAB,
)


class RoleUtilsTests(TestCase):
    domain = 'role-utils'

    @classmethod
    def setUpTestData(cls):
        cls.role1_permissions = HqPermissions(edit_web_users=True)
        cls.role1 = UserRole.create(cls.domain, 'role1', permissions=cls.role1_permissions)

    @classmethod
    def tearDownClass(cls):
        for role in UserRole.objects.get_by_domain(cls.domain):
            role.delete()
        super().tearDownClass()

    def test_init_domain_with_presets(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)
        role_names = set(UserRole.objects.filter(domain=self.domain).values_list("name", flat=True))
        self.assertEqual(role_names, set(UserRolePresets.INITIAL_ROLES) | {'role1'})

        cc_user_default = UserRole.objects.get(domain=self.domain, name=UserRolePresets.MOBILE_WORKER)
        self.assertTrue(cc_user_default.is_commcare_user_default)

    def test_reset_initial_roles_for_domain(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)
        role = UserRole.objects.get(domain=self.domain, name=UserRolePresets.APP_EDITOR)
        original_permissions = role.permissions
        role.set_permissions([])

        self.assertEqual(role.permissions.to_list(), [])

        reset_initial_roles_for_domain(self.domain)

        self.assertEqual(role.permissions, original_permissions)

    def create_commcare_user_default_role(self):
        self.addCleanup(self._delete_presets)
        role_exists = UserRole.objects.filter(domain=self.domain, is_commcare_user_default=True).exists()
        self.assertFalse(role_exists)

        UserRole.commcare_user_default(self.domain)

        role_exists = UserRole.objects.filter(domain=self.domain, is_commcare_user_default=True).exists()
        self.assertTrue(role_exists)

    def test_archive_custom_roles_for_domain(self):
        def _unarchive_custom_role():
            self.role1.is_archived = False
            self.role1.save()

        self.addCleanup(self._delete_presets)
        self.addCleanup(_unarchive_custom_role)
        initialize_domain_with_default_roles(self.domain)

        roles = UserRole.objects.get_by_domain(self.domain, include_archived=True)
        self.assertEqual(len(roles), 6)

        archive_custom_roles_for_domain(self.domain)

        roles = UserRole.objects.get_by_domain(self.domain, include_archived=False)
        self.assertEqual(len(roles), 5)

    def test_unarchive_roles_for_domain(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)

        for role in UserRole.objects.get_by_domain(self.domain):
            role.is_archived = True
            role.save()

        unarchived_role_count = len(UserRole.objects.get_by_domain(self.domain, include_archived=False))
        self.assertEqual(unarchived_role_count, 0)

        unarchive_roles_for_domain(self.domain)

        unarchived_role_count = len(UserRole.objects.get_by_domain(self.domain, include_archived=False))
        self.assertEqual(unarchived_role_count, 6)

    def test_get_custom_roles_for_domain(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)
        roles = get_custom_roles_for_domain(self.domain)
        self.assertEqual([role.name for role in roles], ["role1"])

    def test_enable_attendance_coordinator_role_for_domain(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)

        domain_roles = [role.name for role in UserRole.objects.get_by_domain(self.domain)]
        self.assertFalse(UserRolePresets.ATTENDANCE_COORDINATOR in domain_roles)
        enable_attendance_coordinator_role_for_domain(self.domain)
        domain_roles = [role.name for role in UserRole.objects.get_by_domain(self.domain)]
        self.assertTrue(UserRolePresets.ATTENDANCE_COORDINATOR in domain_roles)

    def test_archive_attendance_coordinator_role_for_domain(self):
        self.addCleanup(self._delete_presets)
        initialize_domain_with_default_roles(self.domain)
        enable_attendance_coordinator_role_for_domain(self.domain)
        archive_attendance_coordinator_role_for_domain(domain=self.domain)

    def _delete_presets(self):
        for role in UserRole.objects.get_by_domain(self.domain):
            if role.id != self.role1.id:
                role.delete()


class TestCommcareAnalyticsRolesByUser(TestCase):

    USERNAME = "username"
    PASSWORD = "***"

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain("domain1")
        cls.user = WebUser.create("domain1", cls.USERNAME, cls.PASSWORD, None, None)
        cls.user.domain_memberships[0].is_admin = True

    @classmethod
    def tearDownClass(cls):
        for role in UserRole.objects.get_by_domain(cls.domain):
            role.delete()

        cls.user.delete(deleted_by_domain=cls.domain.name, deleted_by=None)
        cls.domain.delete()

    def test_admin_user(self):
        self.assertTrue(self.user.get_domain_membership("domain1").is_admin)
        analytics_roles = get_commcare_analytics_roles_by_user_domains(self.user)

        self.assertTrue(analytics_roles["domain1"], COMMCARE_ANALYTICS_USER_PERMISSIONS)

    def test_non_admin_user(self):
        self.user.get_domain_membership("domain1").is_admin = False
        self._set_analytics_roles(analytics_roles=None)

        analytics_roles = get_commcare_analytics_roles_by_user_domains(self.user)
        self.assertEqual(analytics_roles["domain1"], [])

    def test_user_has_limited_roles(self):
        analytics_roles = [
            COMMCARE_ANALYTICS_GAMMA,
            COMMCARE_ANALYTICS_SQL_LAB,
        ]
        self._set_analytics_roles(analytics_roles=analytics_roles)
        self.user.get_domain_membership("domain1")

        analytics_roles = get_commcare_analytics_roles_by_user_domains(self.user)
        self.assertEqual(analytics_roles["domain1"], analytics_roles)

    def _set_analytics_roles(self, analytics_roles=None):
        permissions = HqPermissions()

        if analytics_roles:
            permissions.commcare_analytics_roles = True
            permissions.commcare_analytics_roles_list = analytics_roles

        role = UserRole.create(domain=self.domain, name="CCA Role", permissions=permissions)
        self.user.set_role(self.domain.name, role.get_qualified_id())
