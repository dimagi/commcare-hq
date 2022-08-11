from django.test import TestCase
from field_audit.models import AuditEvent
from nose.tools import nottest

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import HqPermissions

from ..models_role import (
    Permission,
    RoleAssignableBy,
    RolePermission,
    UserRole,
)


class CaseWithDomainAndUser(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        AuditEvent.objects.all().delete()
        cls.domain_name = "pets"
        cls.domain = Domain(name=cls.domain_name)
        cls.domain.save()
        cls.role = UserRole.create(
            cls.domain_name,
            "test-class-role",
            permissions=HqPermissions.min(),  # init with no permissions
        )
        cls.permission = Permission.objects.create(value="do_bupkis")
        cls.class_audit_event_ids = {e.id for e in AuditEvent.objects.all()}

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super().tearDownClass()

    @nottest
    def get_test_audit_events(self, ignore_ids=[]):
        return AuditEvent.objects.exclude(
            id__in=self.class_audit_event_ids.union(ignore_ids),
        )


class TestRoleAssignableBy(CaseWithDomainAndUser):

    def setUp(self):
        self.role.set_assignable_by([self.role.id])
        event, = self.get_test_audit_events()
        self.assignment = RoleAssignableBy.objects.get(id=event.object_pk)

    def test_audit_fields_for_assignableby_create(self):
        setup_event, = self.get_test_audit_events()
        self.assertTrue(setup_event.is_create)
        self.assertEqual(
            "corehq.apps.users.models_role.RoleAssignableBy",
            setup_event.object_class_path,
        )
        self.assertEqual(
            {
                "role": {"new": self.role.id},
                "assignable_by_role": {"new": self.role.id},
            },
            setup_event.delta,
        )

    def test_audit_fields_for_assignableby_delete(self):
        remember = self.assignment.pk
        setup_event, = self.get_test_audit_events()
        self.assignment.delete()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertTrue(event.is_delete)
        self.assertEqual(remember, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.RoleAssignableBy",
            event.object_class_path,
        )
        self.assertEqual(
            {
                "role": {"old": self.role.id},
                "assignable_by_role": {"old": self.role.id},
            },
            event.delta
        )


class TestRolePermission(CaseWithDomainAndUser):

    def setUp(self):
        self.role_permission = RolePermission.objects.create(
            role=self.role,
            permission_fk=self.permission,
        )

    def test_audit_fields_for_rolepermission_create(self):
        setup_event, = self.get_test_audit_events()
        self.assertTrue(setup_event.is_create)
        self.assertEqual(self.role_permission.pk, setup_event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            setup_event.object_class_path,
        )
        # For the sake of this test, we don't care what the default values are
        # for the `allow_all` and `allowed_items` fields, we just care that they
        # were recorded correctly.
        self.assertEqual(
            {
                "role": {"new": self.role.id},
                "allow_all": {"new": self.role_permission.allow_all},
                "allowed_items": {"new": self.role_permission.allowed_items},
                "permission_fk": {"new": self.permission.id},
            },
            setup_event.delta,
        )

    def test_audit_fields_for_rolepermission_update(self):
        setup_event, = self.get_test_audit_events()
        old = self.role_permission.allow_all
        self.role_permission.allow_all = not old  # toggle the value
        self.role_permission.save()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(self.role_permission.pk, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            event.object_class_path,
        )
        self.assertEqual(
            {"allow_all": {"old": old, "new": self.role_permission.allow_all}},
            event.delta,
        )

    def test_audit_fields_for_rolepermission_delete(self):
        setup_event, = self.get_test_audit_events()
        remember = self.role_permission.pk
        self.role_permission.delete()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertTrue(event.is_delete)
        self.assertEqual(remember, event.object_pk)
        self.assertEqual(
            {
                "role": {"old": self.role.id},
                "allow_all": {"old": self.role_permission.allow_all},
                "allowed_items": {"old": self.role_permission.allowed_items},
                "permission_fk": {"old": self.permission.id},
            },
            event.delta,
        )


class TestPermission(CaseWithDomainAndUser):

    def setUp(self):
        self.test_permission = Permission.objects.create(value="edit_bupkis")

    def test_audit_fields_for_permission_create(self):
        setup_event, = self.get_test_audit_events()
        self.assertTrue(setup_event.is_create)
        self.assertEqual(self.test_permission.pk, setup_event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            setup_event.object_class_path,
        )
        self.assertEqual({"value": {"new": "edit_bupkis"}}, setup_event.delta)

    def test_audit_fields_for_permission_update(self):
        setup_event, = self.get_test_audit_events()
        # This isn't an "HQ practical" test because these values don't get
        # changed this way in practice, but this test demonstrates that such a
        # change would be audited if it were to happen.
        self.test_permission.value = "view_bupkis"
        self.test_permission.save()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(self.test_permission.pk, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            event.object_class_path,
        )
        self.assertEqual(
            {"value": {"old": "edit_bupkis", "new": "view_bupkis"}},
            event.delta,
        )

    def test_audit_fields_for_permission_delete(self):
        setup_event, = self.get_test_audit_events()
        remember = self.test_permission.pk
        self.test_permission.delete()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertTrue(event.is_delete)
        self.assertEqual(remember, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            event.object_class_path,
        )
        self.assertEqual({"value": {"old": "edit_bupkis"}}, event.delta)


class TestUserRole(CaseWithDomainAndUser):

    def setUp(self):
        self.test_role = UserRole.create(
            self.domain_name,
            "test-role",
            permissions=HqPermissions.min(),  # init with no permissions
        )
        self.audit_fields = {
            "name",
            "domain",
            "couch_id",
            "is_archived",
            "upstream_id",
            "default_landing_page",
            "is_non_admin_editable",
            "is_commcare_user_default",
        }

    def test_audit_fields_for_userrole_create(self):
        setup_event, = self.get_test_audit_events()
        self.assertTrue(setup_event.is_create)
        self.assertEqual(self.test_role.pk, setup_event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            setup_event.object_class_path,
        )
        self.assertEqual(self.audit_fields, set(setup_event.delta))
        self.assertEqual({"new": "test-role"}, setup_event.delta["name"])
        self.assertEqual({"new": self.domain_name}, setup_event.delta["domain"])

    def test_audit_fields_for_userrole_update(self):
        setup_event, = self.get_test_audit_events()
        old = self.test_role.is_non_admin_editable
        self.test_role.is_non_admin_editable = not old
        self.test_role.save()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(self.test_role.pk, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            setup_event.object_class_path,
        )
        self.assertEqual(
            {"is_non_admin_editable": {"old": old, "new": not old}},
            event.delta,
        )

    def test_audit_fields_for_userrole_delete(self):
        setup_event, = self.get_test_audit_events()
        remember = self.test_role.pk
        self.test_role.delete()
        event, = self.get_test_audit_events([setup_event.id])
        self.assertTrue(event.is_delete)
        self.assertEqual(remember, event.object_pk)
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            event.object_class_path,
        )
        self.assertEqual(self.audit_fields, set(event.delta))
        self.assertEqual({"old": "test-role"}, event.delta["name"])
        self.assertEqual({"old": self.domain_name}, event.delta["domain"])
