from django.core.management import call_command
from django.test import TestCase

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.apps.users.management.commands.populate_user_role import Command
from corehq.apps.users.models import (
    UserRole, Permissions, UserRolePresets, PermissionInfo,
    SQLUserRole, SQLPermission
)
from corehq.apps.users.role_utils import get_custom_roles_for_domain
from dimagi.utils.couch.migration import sync_to_couch_enabled


class UserRoleCouchToSqlTests(TestCase):
    domain = "role-to-sql"

    @classmethod
    def setUpTestData(cls):
        SQLPermission.create_all()
        cls.app_editor = UserRole.create(
            cls.domain,
            UserRolePresets.APP_EDITOR,
            permissions=UserRolePresets.get_permissions(UserRolePresets.APP_EDITOR),
        )
        cls.app_editor_sql = SQLUserRole.objects.get(couch_id=cls.app_editor.get_id)

    @classmethod
    def tearDownClass(cls):
        cls.app_editor.delete()
        super().tearDownClass()

    def tearDown(self):
        for role in SQLUserRole.objects.get_by_domain(self.domain, include_archived=True):
            if role.id != self.app_editor_sql.id:
                role.delete()
        super().tearDown()

    def test_sql_role_couch_to_sql(self):
        couch_role = UserRole(
            domain=self.domain,
            name='test_couch_to_sql',
            permissions=Permissions(
                edit_data=True,
                edit_reports=True,
                access_all_locations=False,
                view_report_list=[
                    'corehq.reports.DynamicReportmaster_report_id'
                ]
            ),
            is_non_admin_editable=False,
            assignable_by=[self.app_editor.get_id],
            upstream_id=self.app_editor.get_id
        )
        couch_role.save()

        sql_role = SQLUserRole.objects.by_couch_id(couch_role.get_id)
        for field in UserRole._migration_get_fields():
            self.assertEqual(getattr(couch_role, field), getattr(sql_role, field))

        # compare json since it gives a nice diff view on failure
        self.assertDictEqual(couch_role.permissions.to_json(), sql_role.permissions.to_json())
        self.assertEqual(couch_role.permissions, sql_role.permissions)
        self.assertEqual(couch_role.assignable_by, sql_role.assignable_by)

    def test_sync_role_sql_to_couch(self):
        sql_role = SQLUserRole(
            domain=self.domain,
            name="test_sql_to_couch",
            default_landing_page=ALL_LANDING_PAGES[0].id,
            is_non_admin_editable=False,
            upstream_id=self.app_editor_sql.couch_id
        )
        sql_role.save(sync_to_couch=False)
        sql_role.set_permissions([
            PermissionInfo(Permissions.edit_data.name),
            PermissionInfo(Permissions.edit_reports.name),
            PermissionInfo(Permissions.view_reports.name, allow=['corehq.reports.DynamicReportmaster_report_id']),
            PermissionInfo(Permissions.view_apps.name),
        ], sync_to_couch=False)

        sql_role.set_assignable_by(list(
            SQLUserRole.objects.filter(couch_id=self.app_editor.get_id).values_list("id", flat=True)
        ), sync_to_couch=False)

        # sync the permissions
        sql_role._migration_do_sync()

        couch_role = UserRole.get(sql_role.couch_id)

        # compare json since it gives a nice diff view on failure
        self.assertDictEqual(couch_role.permissions.to_json(), sql_role.permissions.to_json())
        self.assertEqual(couch_role.permissions, sql_role.permissions)
        self.assertEqual(couch_role.assignable_by, sql_role.assignable_by)

    def test_sync_role_sql_to_couch_set_permissions(self):
        sql_role = SQLUserRole(
            domain=self.domain,
            name="test_sql_to_couch",
            default_landing_page=ALL_LANDING_PAGES[0].id,
            is_non_admin_editable=False,
            upstream_id=self.app_editor_sql.couch_id
        )
        sql_role.save()
        couch_role = UserRole.get(sql_role.couch_id)
        self.assertEqual(couch_role.permissions.to_list(), [])

        sql_role.set_permissions([
            PermissionInfo(Permissions.edit_data.name),
            PermissionInfo(Permissions.edit_reports.name),
            PermissionInfo(Permissions.view_reports.name, allow=['corehq.reports.DynamicReportmaster_report_id']),
            PermissionInfo(Permissions.view_apps.name),
        ])

        couch_role2 = UserRole.get(sql_role.couch_id)
        self.assertDictEqual(couch_role2.permissions.to_json(), sql_role.permissions.to_json())

    def test_sync_role_sql_to_couch_assignable_by(self):
        sql_role = SQLUserRole(
            domain=self.domain,
            name="test_sql_to_couch",
            default_landing_page=ALL_LANDING_PAGES[0].id,
            is_non_admin_editable=False,
            upstream_id=self.app_editor_sql.couch_id
        )
        sql_role.save()
        couch_role = UserRole.get(sql_role.couch_id)
        self.assertEqual(couch_role.assignable_by, [])

        sql_role.set_assignable_by([self.app_editor_sql.id])

        couch_role2 = UserRole.get(sql_role.couch_id)
        self.assertEqual(couch_role2.assignable_by, [self.app_editor.get_id])

    def test_diff_identical(self):
        couch, sql = self._create_identical_objects_for_diff()
        self.assertIsNone(Command.get_diff_as_string(couch.to_json(), sql))

    def test_diff_top_level_attributes(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.domain = "other-domain"
        couch.default_landing_page = "dashboard"
        sql.is_non_admin_editable = True

        self.assertEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            "domain: couch value 'other-domain' != sql value 'role-to-sql'",
            "default_landing_page: couch value 'dashboard' != sql value None",
            "is_non_admin_editable: couch value False != sql value True",
        ])

    def test_diff_upstream_id(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.upstream_id = "abc"
        self.assertEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            f"upstream_id: couch value 'abc' != sql value '{self.app_editor.get_id}'"
        ])

    def test_diff_permissions(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.permissions.edit_reports = False
        couch.permissions.view_web_users = True
        couch.permissions.view_report_list = ['report2']

        sql_permissions = sql.get_permission_infos()
        sql.set_permissions(sql_permissions + [
            PermissionInfo(Permissions.login_as_all_users.name, allow=PermissionInfo.ALLOW_ALL)
        ], sync_to_couch=False)
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            "permissions.edit_reports.allow: couch value None != sql value '*'",
            "permissions.login_as_all_users.allow: couch value None != sql value '*'",
            "permissions.view_reports.allow: couch value ('report2',) != sql value ('report1',)",
            "permissions.view_web_users.allow: couch value '*' != sql value None"
        ])

    def test_diff_assignable_by_couch_None(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.assignable_by = None
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            'assignable_by: 0 in couch != 1 in sql'
        ])

    def test_diff_assignable_by_sql_None(self):
        couch, sql = self._create_identical_objects_for_diff()
        sql.set_assignable_by(None, sync_to_couch=False)
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            'assignable_by: 1 in couch != 0 in sql'
        ])

    def test_diff_assignable_by_sql(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.assignable_by = ["other_id"]
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            f"assignable_by: couch value 'other_id' != sql value '{self.app_editor.get_id}'"
        ])

    def test_to_json(self):
        permissions = Permissions(
            edit_data=True, edit_reports=True, access_all_locations=False,
            view_report_list=['report1']
        )
        couch_role = make_couch_role(
            self.domain, "test-to-json",
            permissions=permissions,
            assignable_by=[self.app_editor.get_id]
        )
        sql_role = couch_role._migration_get_sql_object()
        self.assertIsNotNone(sql_role)

        couch_dict = _drop_couch_only_fields(couch_role.to_json())
        sql_dict = sql_role.to_json()

        # sql uses SQL primary keys, couch uses couch IDs
        couch_assignable_by = couch_dict.pop("assignable_by")
        sql_assignable_by = sql_dict.pop("assignable_by")
        self.assertEqual(len(sql_assignable_by), len(couch_assignable_by))

        self.assertDictEqual(couch_dict, sql_dict)

    def _create_identical_objects_for_diff(self):
        permissions = Permissions(
            edit_data=True, edit_reports=True, access_all_locations=False,
            view_report_list=['report1']
        )
        couch_role = UserRole(
            domain=self.domain,
            name='test_couch_to_sql_diff',
            permissions=permissions,
            is_non_admin_editable=False,
            assignable_by=[self.app_editor.get_id],
            upstream_id=self.app_editor.get_id
        )
        sql_role = SQLUserRole.objects.create(
            domain=self.domain,
            name=couch_role.name,
            is_non_admin_editable=False,
            upstream_id=self.app_editor.get_id
        )
        sql_role.set_permissions(permissions.to_list(), sync_to_couch=False)
        sql_role.set_assignable_by([self.app_editor_sql.id], sync_to_couch=False)
        return couch_role, sql_role


class TestPopulateCommand(TestCase):
    domain = 'test-populate-sql-roles'

    @classmethod
    def setUpClass(cls):
        role1 = UserRole.create(
            cls.domain,
            UserRolePresets.APP_EDITOR,
            permissions=UserRolePresets.get_permissions(UserRolePresets.APP_EDITOR),
        )
        cls.roles = [
            role1,
            UserRole.create(
                cls.domain,
                UserRolePresets.FIELD_IMPLEMENTER,
                permissions=UserRolePresets.get_permissions(UserRolePresets.FIELD_IMPLEMENTER),
                assignable_by=[role1.get_id]
            )
        ]
        cls.roles_by_id = {role._id: role for role in cls.roles}
        SQLUserRole.objects.filter(domain=cls.domain).delete()

    @classmethod
    def tearDownClass(cls):
        for role in UserRole.by_domain(cls.domain):
            role.delete()

    def test_command(self):
        self.assertTrue(sync_to_couch_enabled(SQLUserRole))
        call_command("populate_user_role")
        self.assertTrue(sync_to_couch_enabled(SQLUserRole))
        couch_roles = UserRole.by_domain(self.domain)
        self.assertEqual(len(couch_roles), len(self.roles))
        for role in couch_roles:
            pre_migration_role = self.roles_by_id[role._id]
            self.assertEqual(role.permissions.to_list(), pre_migration_role.permissions.to_list())
            self.assertEqual(role.assignable_by, pre_migration_role.assignable_by)

        sql_roles = SQLUserRole.objects.filter(domain=self.domain).all()
        self.assertEqual(len(sql_roles), len(self.roles))
        for role in sql_roles:
            pre_migration_role = self.roles_by_id[role.couch_id]
            self.assertEqual(role.permissions.to_list(), pre_migration_role.permissions.to_list())
            assignment = [
                assignment.assignable_by_role.couch_id for assignment in role.get_assignable_by()
            ]
            self.assertEqual(assignment, pre_migration_role.assignable_by)


def make_couch_role(domain, name, **kwargs):
    couch_role = UserRole(
        domain=domain,
        name=name,
        **kwargs
    )
    couch_role.save()
    return couch_role


def _drop_couch_only_fields(couch_dict):
    for field in ('_rev', 'doc_type'):
        couch_dict.pop(field, None)
    return couch_dict
