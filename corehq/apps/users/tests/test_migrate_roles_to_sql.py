from django.test import TestCase

from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.apps.users.models import UserRole, Permissions, UserRolePresets, PermissionInfo
from corehq.apps.users.models_sql import SQLUserRole, SQLPermission


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

        sql_roles = list(SQLUserRole.objects.filter(domain=self.domain).all())
        self.assertEqual(2, len(sql_roles))
        sql_role = [role for role in sql_roles if role.name == couch_role.name][0]

        for field in UserRole._migration_get_fields():
            self.assertEqual(getattr(couch_role, field), getattr(sql_role, field))

        self.assertEqual(sql_role.upstream_id, self.app_editor_sql.id)

        # compare json since it gives a nice diff view on failure
        self.assertDictEqual(couch_role.permissions.to_json(), sql_role.permissions.to_json())
        self.assertEqual(couch_role.permissions, sql_role.permissions)
        self.assertEqual(couch_role.assignable_by, sql_role.assignable_by)

    def test_sync_role_sql_to_couch(self):
        self.maxDiff = None
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
        self.assertEqual(couch_role.assignable_by, sql_role.assignable_by)
