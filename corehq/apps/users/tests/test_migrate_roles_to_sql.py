from django.test import TestCase, SimpleTestCase

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.apps.users.management.commands.populate_user_role import Command
from corehq.apps.users.models import UserRole, Permissions, UserRolePresets, PermissionInfo
from corehq.apps.users.models_sql import SQLUserRole, SQLPermission, StaticRole


class UserRoleCouchToSqlTests(TestCase):
    domain = "role-to-sql"

    @classmethod
    def setUpTestData(cls):
        SQLPermission.create_all()
        cls.app_editor = UserRole.get_or_create_with_permissions(
            cls.domain,
            UserRolePresets.get_permissions(UserRolePresets.APP_EDITOR),
            UserRolePresets.APP_EDITOR
        )
        cls.app_editor_sql = SQLUserRole.objects.get(couch_id=cls.app_editor.get_id)

    @classmethod
    def tearDownClass(cls):
        cls.app_editor.delete()
        super().tearDownClass()

    def tearDown(self):
        SQLUserRole.objects.all().delete()
        for role in UserRole.get_custom_roles_by_domain(self.domain):
            role.delete()
        super().tearDown()

    def test_sql_role_couch_to_sql(self):
        couch_role = make_couch_role(self.domain, [self.app_editor.get_id], self.app_editor.get_id)

        sql_roles = list(SQLUserRole.objects.filter(domain=self.domain).all())
        self.assertEqual(2, len(sql_roles))
        sql_role = [role for role in sql_roles if role.name == couch_role.name][0]

        for field in UserRole._migration_get_fields():
            self.assertEqual(getattr(couch_role, field), getattr(sql_role, field))

        self.assertEqual(sql_role.upstream_id, self.app_editor_sql.id)

        # compare json since it gives a nice diff view on failure
        self.assertDictEqual(couch_role.permissions.to_json(), sql_role.permissions.to_json())
        self.assertEqual(couch_role.permissions, sql_role.permissions)
        self.assertEqual(couch_role.assignable_by, [
            assignment.assignable_by_role.couch_id for assignment in sql_role.get_assignable_by()
        ])

    def test_sync_role_sql_to_couch(self):
        sql_role = SQLUserRole(
            domain=self.domain,
            name="test_sql_to_couch",
            default_landing_page=ALL_LANDING_PAGES[0].id,
            is_non_admin_editable=False,
            upstream_id=self.app_editor_sql.id
        )
        sql_role.save()
        sql_role.set_permissions([
            PermissionInfo(Permissions.edit_data.name),
            PermissionInfo(Permissions.edit_reports.name),
            PermissionInfo(Permissions.view_reports.name, allow=['corehq.reports.DynamicReportmaster_report_id']),
            PermissionInfo(Permissions.view_web_apps.name),
        ])

        sql_role.set_assignable_by(list(
            SQLUserRole.objects.filter(couch_id=self.app_editor.get_id).values_list("id", flat=True)
        ))

        # sync the permissions
        sql_role._migration_do_sync()

        couch_roles = UserRole.by_domain(self.domain)
        self.assertEqual(len(couch_roles), 2)
        couch_role = [r for r in couch_roles if r.name == sql_role.name][0]

        for field in SQLUserRole._migration_get_fields():
            self.assertEqual(getattr(couch_role, field), getattr(sql_role, field))

        self.assertEqual(couch_role.upstream_id, self.app_editor.get_id)
        # compare json since it gives a nice diff view on failure
        self.assertDictEqual(couch_role.permissions.to_json(), sql_role.permissions.to_json())
        self.assertEqual(couch_role.permissions, sql_role.permissions)
        self.assertEqual(couch_role.assignable_by, [
            assignment.assignable_by_role.couch_id for assignment in sql_role.get_assignable_by()
        ])

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
        ])
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
        sql.set_assignable_by(None)
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            'assignable_by: 1 in couch != 0 in sql'
        ])

    def test_diff_assignable_by_sql(self):
        couch, sql = self._create_identical_objects_for_diff()
        couch.assignable_by = ["other_id"]
        self.assertListEqual(Command.get_filtered_diffs(couch.to_json(), sql), [
            f"assignable_by: couch value 'other_id' != sql value '{self.app_editor.get_id}'"
        ])

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
            upstream_id=self.app_editor_sql.id
        )
        sql_role.set_permissions(permissions.to_list())
        sql_role.set_assignable_by([self.app_editor_sql.id])
        return couch_role, sql_role


def make_couch_role(domain, name, **kwargs):
    couch_role = UserRole(
        domain=domain,
        name=name,
        **kwargs
    )
    couch_role.save()

    def test_to_json(self):
        couch_role = make_couch_role(self.domain, [self.app_editor.get_id], self.app_editor.get_id)
        sql_role = couch_role._migration_get_sql_object()
        self.assertIsNotNone(sql_role)

        couch_dict = _drop_couch_only_fields(couch_role.to_json())
        sql_dict = sql_role.to_json()

        # this field differs between the 2, each is the ID in their respective DBs
        couch_dict.pop("upstream_id")
        sql_dict.pop("upstream_id")
        self.assertDictEqual(couch_dict, sql_dict)


class TestStaticRoles(SimpleTestCase):
    domain = "static-role-test"

    def test_static_role_default(self):
        static_dict = StaticRole.domain_default(self.domain).to_json()
        couch_dict = UserRole(domain=self.domain, name=None, permissions=Permissions()).to_json()
        _drop_couch_only_fields(couch_dict)
        self.assertDictEqual(couch_dict, static_dict)

    def test_static_role_admin(self):
        static_admin_role = StaticRole.domain_admin(self.domain)
        couch_dict = UserRole(domain=self.domain, name="Admin", permissions=Permissions.max()).to_json()
        _drop_couch_only_fields(couch_dict)
        self.assertDictEqual(couch_dict, static_admin_role.to_json())
        self.assertEqual(static_admin_role.get_qualified_id(), "admin")


def _drop_couch_only_fields(couch_dict):
    for field in ('_rev', 'doc_type'):
        couch_dict.pop(field, None)
    return couch_dict


def make_couch_role(domain, assignable_by, upstream_id):
    role = UserRole(
        domain=domain,
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
        assignable_by=assignable_by,
        upstream_id=upstream_id
    )
    role.save()
    return role
