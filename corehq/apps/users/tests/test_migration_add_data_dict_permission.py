from django.db.models import Q
from django.test import TestCase
from unittest.mock import patch

from corehq.apps.users.models import HqPermissions
from corehq.apps.users.models_role import UserRole, RolePermission, Permission
from corehq.apps.users.management.commands.add_data_dict_permissions import (
    build_role_can_edit_commcare_data_q_object,
    build_role_can_export_data_q_object,
    build_role_can_download_data_files_q_object,
    role_can_view_data_tab,
    role_already_migrated,
    get_user_role_ids_to_migrate
)
from corehq.apps.users.permissions import EXPORT_PERMISSIONS


class TestMigrationQuery(TestCase):
    domain = "test-query"

    @classmethod
    def setUpTestData(cls):
        Permission.create_all()

    def setUp(self):
        patcher1 = patch(
            ('corehq.apps.users.management.commands.add_data_dict_permissions'
            '.DATA_FILE_DOWNLOAD.get_enabled_domains'),
            return_value=[self.domain]
        )
        patcher2 = patch(
            ('corehq.apps.users.management.commands.add_data_dict_permissions'
             '.DATA_DICTIONARY.get_enabled_domains'),
            return_value=[]
        )
        patcher3 = patch(
            ('corehq.apps.users.management.commands.add_data_dict_permissions'
             '.get_domains_with_privilege'),
            return_value=[self.domain]
        )
        patcher1.start()
        patcher2.start()
        patcher3.start()
        self.role = UserRole(domain=self.domain, name="role1")
        self.role.save()
        self.addCleanup(self.role.delete)
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)

    def test_role_has_edit_data_permission(self):
        self.role.rolepermission_set.set([
            RolePermission(permission=HqPermissions.edit_data.name)
        ], bulk=False)

        can_edit_commcare_data = build_role_can_edit_commcare_data_q_object()
        queried_role_ids = self._query_role(can_edit_commcare_data)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_has_all_reports_permission(self):
        self.role.rolepermission_set.set([
            RolePermission(permission=HqPermissions.view_reports.name)
        ], bulk=False)

        self.can_export_data = build_role_can_export_data_q_object()
        queried_role_ids = self._query_role(self.can_export_data)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_has_export_reports_permission(self):
        self.role.rolepermission_set.set([
            RolePermission(permission=HqPermissions.view_reports.name, allow_all=False,
                allowed_items=list(EXPORT_PERMISSIONS))
        ], bulk=False)

        self.can_export_data = build_role_can_export_data_q_object()
        queried_role_ids = self._query_role(self.can_export_data)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_has_download_data_files_permission(self):
        self.role.rolepermission_set.set([
            RolePermission(permission=HqPermissions.view_file_dropzone.name)
        ], bulk=False)

        self.can_download_data_files = build_role_can_download_data_files_q_object()
        queried_role_ids = self._query_role(self.can_download_data_files)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_can_view_data_tab_all_permissions(self):
        perms = HqPermissions.max()
        setattr(perms, HqPermissions.view_data_dict.name, False)
        setattr(perms, HqPermissions.edit_data_dict.name, False)
        self.role.set_permissions(perms.to_list())

        can_view_data_tab = role_can_view_data_tab()
        queried_role_ids = self._query_role(can_view_data_tab)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_can_not_view_data_tab(self):
        perms = HqPermissions.max()
        perms = self._revoke_permissions_to_access_data_dict(perms)
        self.role.set_permissions(perms.to_list())

        can_not_view_data_tab = ~role_can_view_data_tab()
        queried_role_ids = self._query_role(can_not_view_data_tab)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_role_already_migrated(self):
        self.role.rolepermission_set.set([
            RolePermission(permission=HqPermissions.edit_data_dict.name)
        ], bulk=False)
        role_migrated = role_already_migrated()
        queried_role_ids = self._query_role(role_migrated)
        self.assertQuerysetEqual(queried_role_ids, [self.role.id], ordered=False)

    def test_get_user_roles_to_migrate(self):
        perms = HqPermissions.max()
        self.role.set_permissions(perms.to_list())

        user_roles_to_migrate_ids = get_user_role_ids_to_migrate()
        self.assertFalse(user_roles_to_migrate_ids.exists())

        setattr(perms, HqPermissions.view_data_dict.name, False)
        setattr(perms, HqPermissions.edit_data_dict.name, False)
        self.role.set_permissions(perms.to_list())
        self.assertCountEqual(user_roles_to_migrate_ids, [self.role.id])

    def _query_role(self, filter_query: Q):
        user_roles_can_view_data_tab_id = (UserRole.objects
                    .filter(domain=self.domain)
                    .filter(filter_query)
                    .distinct()
                    .values_list("id", flat=True)
        )
        return user_roles_can_view_data_tab_id

    def _revoke_permissions_to_access_data_dict(self, perms: HqPermissions):
        permissions = {
            HqPermissions.view_data_dict.name: False,
            HqPermissions.edit_data_dict.name: False,
            HqPermissions.edit_data.name: False,
            HqPermissions.view_reports.name: False,
            HqPermissions.view_report_list.name: ["not_export_permission"],
            HqPermissions.view_file_dropzone.name: False,
            HqPermissions.edit_file_dropzone.name: False
        }
        for name, value in permissions.items():
            setattr(perms, name, value)

        return perms
