from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from field_audit.models import AuditEvent

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import PermissionInfo
from corehq.apps.users.models_role import Permission, UserRole


class BaseRoleHistoryTest(TestCase):

    domain_name = "test-role-history"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        AuditEvent.objects.all().delete()
        cls.domain = Domain.get_or_create_with_name(
            name=cls.domain_name, is_active=True,
        )
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)

    def _call_command(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command("role_permission_history", *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue()

    def setUp(self):
        super().setUp()
        AuditEvent.objects.all().delete()


class TestListRoles(BaseRoleHistoryTest):

    def test_list_roles(self):
        role = UserRole.create(self.domain_name, "Supervisor")
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--list")
        assert "Supervisor" in output
        assert f"id={role.id}" in output
        assert f"couch_id={role.couch_id}" in output

    def test_list_roles_shows_archived(self):
        role = UserRole.create(self.domain_name, "Old Role", is_archived=True)
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--list")
        assert "Old Role" in output
        assert "(archived)" in output

    def test_list_roles_empty_domain(self):
        output = self._call_command("nonexistent-domain", "--list")
        assert "No roles found" in output


class TestGetRoleErrors(BaseRoleHistoryTest):

    def test_nonexistent_role_name(self):
        with pytest.raises(CommandError, match="No role found") as exc_info:
            self._call_command(self.domain_name, "--role-name", "Nonexistent")
        assert "--list" in str(exc_info.value)

    def test_nonexistent_role_id(self):
        with pytest.raises(CommandError, match="No role found"):
            self._call_command(self.domain_name, "--role-id", "999999")

    def test_nonexistent_couch_id(self):
        with pytest.raises(CommandError, match="No role found") as exc_info:
            self._call_command(self.domain_name, "--role-id", "abc123def456")
        assert "couch_id" in str(exc_info.value)

    def test_lookup_by_couch_id(self):
        role = UserRole.create(self.domain_name, "Couch Lookup")
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--role-id", role.couch_id)
        assert "Couch Lookup" in output

    def test_role_id_wrong_domain(self):
        role = UserRole.create(self.domain_name, "Wrong Domain")
        self.addCleanup(role.delete)
        with pytest.raises(CommandError, match="No role found"):
            self._call_command("other-domain", "--role-id", str(role.id))

    def test_couch_id_wrong_domain(self):
        role = UserRole.create(self.domain_name, "Wrong Domain Couch")
        self.addCleanup(role.delete)
        with pytest.raises(CommandError, match="No role found"):
            self._call_command("other-domain", "--role-id", role.couch_id)

    def test_ambiguous_role_name(self):
        role1 = UserRole.create(self.domain_name, "Duplicate")
        role2 = UserRole.create(self.domain_name, "Duplicate")
        self.addCleanup(role1.delete)
        self.addCleanup(role2.delete)
        with pytest.raises(CommandError, match="Multiple roles found") as exc_info:
            self._call_command(self.domain_name, "--role-name", "Duplicate")
        assert "--role-id" in str(exc_info.value)


class TestRoleCreatedEvent(BaseRoleHistoryTest):

    def test_shows_role_created(self):
        role = UserRole.create(self.domain_name, "New Role")
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Role CREATED" in output
        assert "name: New Role" in output

    def test_shows_role_metadata_change(self):
        role = UserRole.create(self.domain_name, "Editable Role")
        self.addCleanup(role.delete)
        role.is_non_admin_editable = True
        role.save()
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "is_non_admin_editable: False \u2192 True" in output


class TestPermissionEvents(BaseRoleHistoryTest):

    def test_permission_granted(self):
        role = UserRole.create(self.domain_name, "Grant Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.first()
        role.set_permissions([PermissionInfo(perm.value)])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Permission GRANTED" in output
        assert perm.value in output
        assert "items:" not in output

    def test_permission_granted_with_items(self):
        role = UserRole.create(self.domain_name, "Items Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.get(value="view_reports")
        role.set_permissions([PermissionInfo(perm.value, allow=["item_a", "item_b"])])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Permission GRANTED" in output
        assert "item_a" in output
        assert "item_b" in output

    def test_permission_revoked(self):
        role = UserRole.create(self.domain_name, "Revoke Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.first()
        role.set_permissions([PermissionInfo(perm.value)])
        role.set_permissions([])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Permission REVOKED" in output
        assert perm.value in output

    def test_permission_changed(self):
        role = UserRole.create(self.domain_name, "Change Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.get(value="view_reports")
        role.set_permissions([PermissionInfo(perm.value)])
        # Re-fetch the RolePermission after set_permissions (which deletes and recreates)
        rp = role.rolepermission_set.get(permission_fk=perm)
        rp.allow_all = False
        rp.save()
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Permission CHANGED: view_reports" in output
        assert "allow_all: True \u2192 False" in output
        assert "unknown" not in output


class TestAssignableByEvents(BaseRoleHistoryTest):

    def test_assignable_by_added(self):
        role = UserRole.create(self.domain_name, "Assign Test")
        self.addCleanup(role.delete)
        role.set_assignable_by([role.id])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Assignable by ADDED" in output
        assert "Assign Test" in output

    def test_assignable_by_removed(self):
        role = UserRole.create(self.domain_name, "Unassign Test")
        self.addCleanup(role.delete)
        role.set_assignable_by([role.id])
        role.set_assignable_by([])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "Assignable by REMOVED" in output


class TestNoEvents(BaseRoleHistoryTest):

    def test_no_events(self):
        role = UserRole.create(self.domain_name, "Empty Test")
        self.addCleanup(role.delete)
        # Clear all events including the create event
        AuditEvent.objects.all().delete()
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        assert "No audit events found" in output


class TestChronologicalOrder(BaseRoleHistoryTest):

    def test_events_in_chronological_order(self):
        role = UserRole.create(self.domain_name, "Chrono Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.first()
        role.set_permissions([PermissionInfo(perm.value)])
        role.set_permissions([])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        created_pos = output.index("Role CREATED")
        granted_pos = output.index("Permission GRANTED")
        revoked_pos = output.index("Permission REVOKED")
        assert created_pos < granted_pos < revoked_pos
