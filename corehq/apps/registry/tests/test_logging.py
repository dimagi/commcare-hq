import uuid
from django.test import TestCase
from corehq.apps.app_manager.models import Application

from corehq.apps.domain.shortcuts import create_user
from corehq.apps.domain.tests.test_utils import test_domain
from corehq.apps.registry.models import RegistryAuditLog, RegistryInvitation
from corehq.apps.registry.tests.utils import Invitation, create_registry_for_test
from corehq.apps.registry.utils import DataRegistryCrudHelper
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater


class RegistryLoggingTests(TestCase):
    domain = "registry-test-logging"

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("admin", "123")

    def setUp(self):
        self.registry = create_registry_for_test(
            self.user, self.domain, invitations=[
                Invitation("A", accepted=False, rejected=False),
            ]
        )
        self.helper = DataRegistryCrudHelper(self.domain, self.registry.slug, self.user)

    def test_log_activate_deactivate(self):
        self.assertTrue(self.registry.is_active)

        self.helper.deactivate()
        self.registry.refresh_from_db()
        self.assertFalse(self.registry.is_active)

        self.helper.activate()
        self.registry.refresh_from_db()
        self.assertTrue(self.registry.is_active)

        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_DEACTIVATED),
            (self.domain, RegistryAuditLog.ACTION_ACTIVATED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_log_invitation_accept_reject(self):
        self.helper.accept_invitation("A")

        invitation = self.registry.invitations.filter(domain="A").get()
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_ACCEPTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

        self.helper.reject_invitation("A")
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_REJECTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_REJECTED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

        self.helper.accept_invitation("A")
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_ACCEPTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_REJECTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_update_schema_log(self):
        self.helper.update_schema([{"case_type": "a"}])
        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_SCHEMA_CHANGED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_create_invitation_logging(self):
        with test_domain(name="B", skip_full_delete=True):
            self.helper.get_or_create_invitation("B")
            self._assertLogs([
                (self.domain, RegistryAuditLog.ACTION_INVITATION_ADDED),
                ("B", RegistryAuditLog.ACTION_INVITATION_ADDED),
            ])

    def test_remove_invitation_logging(self):
        invitation = self.registry.invitations.create(domain="B")
        self.helper.remove_invitation("B", invitation.id)
        self._assertLogs([
            ("B", RegistryAuditLog.ACTION_INVITATION_REMOVED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_create_grant_logging(self):
        self.registry.invitations.create(domain="B")
        self.helper.get_or_create_grant(self.domain, ["B"])
        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_GRANT_ADDED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_remove_grant_logging(self):
        self.registry.invitations.create(domain="B")
        grant = self.registry.grants.create(from_domain=self.domain, to_domains=["B"])
        self.helper.remove_grant(self.domain, grant.id)
        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_GRANT_REMOVED),
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_log_data_access_with_repeater(self):
        connx = ConnectionSettings.objects.create(domain=self.domain, url='http://fake.com')
        repeater = FormRepeater(
            domain=self.domain,
            connection_settings=connx,
        )
        repeater.save()
        self.registry.logger.data_accessed(self.user, self.domain, repeater)
        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_DATA_ACCESSED)
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def test_log_data_access_with_application(self):
        app = Application.new_app(self.domain, 'Test App')
        app._id = uuid.uuid4().hex
        self.registry.logger.data_accessed(self.user, self.domain, app)
        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_DATA_ACCESSED)
        ], ignore_actions=[RegistryAuditLog.ACTION_INVITATION_ADDED])

    def _assertLogs(self, expected_actions, ignore_actions=None):
        actions = list(
            RegistryAuditLog.objects
            .filter(registry=self.registry, )
            .order_by('date')
            .values_list("domain", "action")
        )
        if ignore_actions:
            actions = [action for action in actions if action[1] not in ignore_actions]
        self.assertEqual(expected_actions, actions)
