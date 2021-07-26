from django.test import TestCase

from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.exceptions import RegistryAccessDenied
from corehq.apps.registry.models import DataRegistry, RegistryAuditLog, RegistryInvitation
from corehq.apps.registry.tests.utils import Invitation, create_registry_for_test, Grant


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

    def test_log_activate_deactivate(self):
        self.assertTrue(self.registry.is_active)

        self.registry.deactivate(self.user)
        self.assertFalse(self.registry.is_active)

        self.registry.activate(self.user)
        self.assertTrue(self.registry.is_active)

        self._assertLogs([
            (self.domain, RegistryAuditLog.ACTION_DEACTIVATED),
            (self.domain, RegistryAuditLog.ACTION_ACTIVATED),
        ])

    def test_log_invitation_accept_reject(self):
        invitation = self.registry.invitations.filter(domain="A").get()
        invitation.accept(self.user)
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_ACCEPTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
        ])

        invitation.reject(self.user)
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_REJECTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_REJECTED),
        ])

        invitation.accept(self.user)
        self.assertEqual(invitation.status, RegistryInvitation.STATUS_ACCEPTED)

        self._assertLogs([
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_REJECTED),
            ("A", RegistryAuditLog.ACTION_INVITATION_ACCEPTED),
        ])

    def _assertLogs(self, expected_actions):
        actions = list(
            RegistryAuditLog.objects
            .filter(registry=self.registry)
            .order_by('date')
            .values_list("domain", "action")
        )
        self.assertEqual(expected_actions, actions)
