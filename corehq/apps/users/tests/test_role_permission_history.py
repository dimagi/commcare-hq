from io import StringIO

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
        self.assertIn("Supervisor", output)
        self.assertIn(f"id={role.id}", output)

    def test_list_roles_shows_archived(self):
        role = UserRole.create(self.domain_name, "Old Role", is_archived=True)
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--list")
        self.assertIn("Old Role", output)
        self.assertIn("(archived)", output)

    def test_list_roles_empty_domain(self):
        output = self._call_command("nonexistent-domain", "--list")
        self.assertIn("No roles found", output)


class TestGetRoleErrors(BaseRoleHistoryTest):

    def test_nonexistent_role_name(self):
        with self.assertRaises(CommandError) as ctx:
            self._call_command(self.domain_name, "--role-name", "Nonexistent")
        self.assertIn("No role found", str(ctx.exception))
        self.assertIn("--list", str(ctx.exception))

    def test_nonexistent_role_id(self):
        with self.assertRaises(CommandError) as ctx:
            self._call_command(self.domain_name, "--role-id", "999999")
        self.assertIn("No role found", str(ctx.exception))

    def test_ambiguous_role_name(self):
        role1 = UserRole.create(self.domain_name, "Duplicate")
        role2 = UserRole.create(self.domain_name, "Duplicate")
        self.addCleanup(role1.delete)
        self.addCleanup(role2.delete)
        with self.assertRaises(CommandError) as ctx:
            self._call_command(self.domain_name, "--role-name", "Duplicate")
        self.assertIn("Multiple roles found", str(ctx.exception))
        self.assertIn("--role-id", str(ctx.exception))


class TestRoleCreatedEvent(BaseRoleHistoryTest):

    def test_shows_role_created(self):
        role = UserRole.create(self.domain_name, "New Role")
        self.addCleanup(role.delete)
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Role CREATED", output)
        self.assertIn("name: New Role", output)

    def test_shows_role_metadata_change(self):
        role = UserRole.create(self.domain_name, "Editable Role")
        self.addCleanup(role.delete)
        role.is_non_admin_editable = True
        role.save()
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("is_non_admin_editable: False \u2192 True", output)


class TestPermissionEvents(BaseRoleHistoryTest):

    def test_permission_granted(self):
        role = UserRole.create(self.domain_name, "Grant Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.first()
        role.set_permissions([PermissionInfo(perm.value)])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Permission GRANTED", output)
        self.assertIn(perm.value, output)
        self.assertIn("allow all", output)

    def test_permission_granted_with_items(self):
        role = UserRole.create(self.domain_name, "Items Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.get(value="view_reports")
        role.set_permissions([PermissionInfo(perm.value, allow=["item_a", "item_b"])])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Permission GRANTED", output)
        self.assertIn("item_a", output)
        self.assertIn("item_b", output)

    def test_permission_revoked(self):
        role = UserRole.create(self.domain_name, "Revoke Test")
        self.addCleanup(role.delete)
        perm = Permission.objects.first()
        role.set_permissions([PermissionInfo(perm.value)])
        role.set_permissions([])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Permission REVOKED", output)
        self.assertIn(perm.value, output)

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
        self.assertIn("Permission CHANGED", output)
        self.assertIn("allow_all: True \u2192 False", output)


class TestAssignableByEvents(BaseRoleHistoryTest):

    def test_assignable_by_added(self):
        role = UserRole.create(self.domain_name, "Assign Test")
        self.addCleanup(role.delete)
        role.set_assignable_by([role.id])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Assignable by ADDED", output)
        self.assertIn("Assign Test", output)

    def test_assignable_by_removed(self):
        role = UserRole.create(self.domain_name, "Unassign Test")
        self.addCleanup(role.delete)
        role.set_assignable_by([role.id])
        role.set_assignable_by([])
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("Assignable by REMOVED", output)


class TestNoEvents(BaseRoleHistoryTest):

    def test_no_events(self):
        role = UserRole.create(self.domain_name, "Empty Test")
        self.addCleanup(role.delete)
        # Clear all events including the create event
        AuditEvent.objects.all().delete()
        output = self._call_command(self.domain_name, "--role-id", str(role.id))
        self.assertIn("No audit events found", output)


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
        self.assertLess(created_pos, granted_pos)
        self.assertLess(granted_pos, revoked_pos)
