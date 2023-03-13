from django.test import SimpleTestCase, TestCase
from field_audit.models import AuditEvent
from nose.tools import nottest

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import HqPermissions

from ..models import PermissionInfo
from ..models_role import (
    Permission,
    # RolePermission,
    UserRole,
)


class BaseEventSetupCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        AuditEvent.objects.all().delete()

    def setUp(self):
        super().setUp()
        self.setup_audited_models()
        self.setup_audit_events = AuditEvent.objects.all()
        self.setup_event_ids = set(self.setup_audit_events.values_list("id", flat=True))

    def setup_audited_models(self):
        raise NotImplementedError("BaseEventSetupCase is abstract")

    @nottest
    def get_test_audit_events(self, ignore_ids=[]):
        return AuditEvent.objects.exclude(
            id__in=self.setup_event_ids.union(ignore_ids),
        )


class CaseWithDomainAndRole(BaseEventSetupCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_name = "pets"
        cls.role_name = "test-role"
        cls.domain = Domain.get_or_create_with_name(name=cls.domain_name, is_active=True)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)

    def setup_audited_models(self):
        self.role = UserRole.create(
            self.domain_name,
            self.role_name,
            permissions=HqPermissions.min(),  # init with no permissions
        )


class TestUserRole(CaseWithDomainAndRole):

    audit_fields = {
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
        setup_event, = self.setup_audit_events
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            setup_event.object_class_path,
        )
        self.assertEqual(self.role.pk, setup_event.object_pk)
        self.assertTrue(setup_event.is_create)
        self.assertEqual(self.audit_fields, set(setup_event.delta))
        self.assertEqual({"new": self.role_name}, setup_event.delta["name"])
        self.assertEqual({"new": self.domain_name}, setup_event.delta["domain"])

    def test_audit_fields_for_userrole_update(self):
        previous = self.role.is_non_admin_editable
        self.role.is_non_admin_editable = not previous
        self.role.save()
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            event.object_class_path,
        )
        self.assertEqual(self.role.pk, event.object_pk)
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(
            {"is_non_admin_editable": {"old": previous, "new": not previous}},
            event.delta,
        )

    def test_audit_fields_for_userrole_delete(self):
        remember = self.role.pk
        self.role.delete()
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.UserRole",
            event.object_class_path,
        )
        self.assertEqual(remember, event.object_pk)
        self.assertTrue(event.is_delete)
        self.assertEqual(self.audit_fields, set(event.delta))
        self.assertEqual({"old": self.role_name}, event.delta["name"])
        self.assertEqual({"old": self.domain_name}, event.delta["domain"])


class TestRoleAssignableBy(CaseWithDomainAndRole):

    def setup_audited_models(self):
        super().setup_audited_models()
        AuditEvent.objects.all().delete()  # discard the UserRole event
        self.role.set_assignable_by([self.role.id])

    def test_audit_fields_for_assignableby_create(self):
        setup_event, = self.setup_audit_events
        self.assertEqual(
            "corehq.apps.users.models_role.RoleAssignableBy",
            setup_event.object_class_path,
        )
        self.assertTrue(setup_event.is_create)
        self.assertEqual(
            {
                "role": {"new": self.role.id},
                "assignable_by_role": {"new": self.role.id},
            },
            setup_event.delta,
        )

    def test_audit_fields_for_assignableby_delete(self):
        assignment, = self.role.get_assignable_by()
        assignment_pk = assignment.pk  # will be cleared when deleted
        self.role.set_assignable_by([])  # calls RoleAssignableBy.<QuerySet>.delete()
        event, = self.get_test_audit_events()
        self.assertTrue(event.is_delete)
        self.assertEqual(assignment_pk, event.object_pk)
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


class TestRolePermission(CaseWithDomainAndRole):

    def setup_audited_models(self):
        super().setup_audited_models()
        AuditEvent.objects.all().delete()  # discard the UserRole event
        self.permission = Permission.objects.first()  # fetch any existing one
        self.permission_info = PermissionInfo(self.permission.value)
        self.role.set_permissions([self.permission_info])
        self.role_permission, = self.role.rolepermission_set.all()

    def test_audit_fields_for_rolepermission_create(self):
        setup_event, = self.setup_audit_events
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            setup_event.object_class_path,
        )
        self.assertEqual(self.role_permission.pk, setup_event.object_pk)
        self.assertTrue(setup_event.is_create)
        # For the sake of this test, we don't care what the default values are
        # for the `allow_all` and `allowed_items` fields, we just care that they
        # were recorded correctly.
        self.assertEqual(
            {
                "role": {"new": self.role.id},
                "allow_all": {"new": self.role_permission.allow_all},
                "allowed_items": {"new": self.role_permission.allowed_items},
                "permission_fk": {"new": self.permission.pk},
            },
            setup_event.delta,
        )

    def test_audit_fields_for_rolepermission_direct_edit(self):
        # This isn't an "HQ practical" test because these values don't get
        # changed this way in practice, but this test demonstrates that such a
        # change would be audited if it were to happen.
        previous = self.role_permission.allow_all
        self.role_permission.allow_all = not previous
        self.role_permission.save()
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            event.object_class_path,
        )
        self.assertEqual(self.role_permission.pk, event.object_pk)
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(
            {"allow_all": {"old": previous, "new": self.role_permission.allow_all}},
            event.delta,
        )

    def test_audit_fields_for_rolepermission_set_new(self):
        # fetch any other existing permission
        permission_x = Permission.objects.exclude(id=self.permission.id).first()
        permission_info_x = PermissionInfo(permission_x.value)
        self.role.set_permissions([permission_info_x])
        role_permission_x, = self.role.rolepermission_set.all()
        removed, added = self.get_test_audit_events().order_by("is_create")
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            removed.object_class_path,
            added.object_class_path,
        )
        # removed
        self.assertEqual(self.role_permission.pk, removed.object_pk)
        self.assertTrue(removed.is_delete)
        self.assertEqual(
            {
                "role": {"old": self.role.id},
                "allow_all": {"old": self.role_permission.allow_all},
                "allowed_items": {"old": self.role_permission.allowed_items},
                "permission_fk": {"old": self.permission.pk},
            },
            removed.delta,
        )
        # added
        self.assertEqual(role_permission_x.pk, added.object_pk)
        self.assertTrue(added.is_create)
        self.assertEqual(
            {
                "role": {"new": self.role.id},
                "allow_all": {"new": role_permission_x.allow_all},
                "allowed_items": {"new": role_permission_x.allowed_items},
                "permission_fk": {"new": permission_x.pk},
            },
            added.delta,
        )

    def test_audit_fields_for_rolepermission_delete(self):
        remember_me = self.role_permission.pk
        self.role.set_permissions([])
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.RolePermission",
            event.object_class_path,
        )
        self.assertEqual(remember_me, event.object_pk)
        self.assertTrue(event.is_delete)
        self.assertEqual(
            {
                "role": {"old": self.role.id},
                "allow_all": {"old": self.role_permission.allow_all},
                "allowed_items": {"old": self.role_permission.allowed_items},
                "permission_fk": {"old": self.permission.id},
            },
            event.delta,
        )


class TestPermission(BaseEventSetupCase):

    @classmethod
    def setup_audited_models(cls):
        cls.permission = Permission.objects.create(value="do_bupkis")

    def test_audit_fields_for_permission_create(self):
        setup_event, = self.setup_audit_events
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            setup_event.object_class_path,
        )
        self.assertEqual(self.permission.pk, setup_event.object_pk)
        self.assertTrue(setup_event.is_create)
        self.assertEqual({"value": {"new": "do_bupkis"}}, setup_event.delta)

    def test_audit_fields_for_permission_update(self):
        # This isn't an "HQ practical" test because these values don't get
        # changed this way in practice, but this test demonstrates that such a
        # change would be audited if it were to happen.
        self.permission.value = "do_everything"
        self.permission.save()
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            event.object_class_path,
        )
        self.assertEqual(self.permission.pk, event.object_pk)
        self.assertFalse(event.is_create)
        self.assertFalse(event.is_delete)
        self.assertEqual(
            {"value": {"old": "do_bupkis", "new": "do_everything"}},
            event.delta,
        )

    def test_audit_fields_for_permission_delete(self):
        remember = self.permission.pk
        self.permission.delete()
        event, = self.get_test_audit_events()
        self.assertEqual(
            "corehq.apps.users.models_role.Permission",
            event.object_class_path,
        )
        self.assertEqual(remember, event.object_pk)
        self.assertTrue(event.is_delete)
        self.assertEqual({"value": {"old": "do_bupkis"}}, event.delta)


class HqPermissionsTest(SimpleTestCase):

    def setUp(self):
        self.hq_permissions = HqPermissions()
        self.permission_names = self.hq_permissions.permission_names()
        self.permissions = {name: getattr(self.hq_permissions, name) for name in self.permission_names}

    def test_permissions_default(self):
        default_true_permissions = ['access_all_locations', 'report_an_issue']
        for name, value in self.permissions.items():
            if name not in default_true_permissions:
                self.assertFalse(value)
            else:
                self.assertTrue(value)

    def test_view_allowed_when_edit_allowed(self):
        edit_view_permission_dict = {
            'edit_web_users': 'view_web_users',
            'edit_commcare_users': 'view_commcare_users',
            'edit_groups': 'view_groups',
            'edit_locations': 'view_locations',
            'edit_data_dict': 'view_data_dict',
            'edit_apps': 'view_apps',
        }
        for edit_permission_name in edit_view_permission_dict:
            setattr(self.hq_permissions, edit_permission_name, True)
        self.hq_permissions.normalize()
        for view_permission_name in edit_view_permission_dict.values():
            self.assertTrue(getattr(self.hq_permissions, view_permission_name))

    def test_download_reports_removed_when_view_reports_false(self):
        self.hq_permissions.view_reports = False
        self._check_normalized_permission("download_reports", expect_changed=True)

    def test_download_reports_not_removed_when_view_reports_true(self):
        self.hq_permissions.view_reports = True
        self._check_normalized_permission("download_reports", expect_changed=False)

    def test_download_reports_not_removed_when_view_reports_list(self):
        self.hq_permissions.view_reports = False
        self.hq_permissions.view_report_list = ["a"]
        self._check_normalized_permission("download_reports", expect_changed=False)

    def _check_normalized_permission(self, permission, initial_value=True, expect_changed=True):
        setattr(self.hq_permissions, permission, initial_value)
        self.hq_permissions.normalize()
        if expect_changed:
            self.assertNotEqual(getattr(self.hq_permissions, permission), initial_value)
        else:
            self.assertEqual(getattr(self.hq_permissions, permission), initial_value)

        # Test that the inverse value isn't affected
        setattr(self.hq_permissions, permission, not initial_value)
        self.hq_permissions.normalize()
        self.assertEqual(getattr(self.hq_permissions, permission), not initial_value)
