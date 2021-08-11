from django.test import TestCase

from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.exceptions import RegistryAccessDenied
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.tests.utils import Invitation, create_registry_for_test, Grant


class RegistryModelsTests(TestCase):
    domain = "registry-test"

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("admin", "123")
        cls.active = DataRegistry.objects.create(domain=cls.domain, name="active")
        cls.inactive = DataRegistry.objects.create(domain=cls.domain, name="inactive", is_active=False)

    def test_slug_unique_per_domain(self):
        r1 = DataRegistry.objects.create(domain=self.domain, name="patient registry")
        r2 = DataRegistry.objects.create(domain=self.domain, name="the patient registry")
        r3 = DataRegistry.objects.create(domain="other_domain", name="the patient registry")
        self.assertEqual(r1.slug, "patient-registry")
        self.assertEqual(r2.slug, "patient-registry-2")
        self.assertEqual(r3.slug, "patient-registry")

    def test_get_owned(self):
        self.assertEqual(
            {self.active.id, self.inactive.id},
            {reg.id for reg in DataRegistry.objects.owned_by_domain(self.domain)},
        )
        self.assertEqual(
            {self.active.id},
            {reg.id for reg in DataRegistry.objects.owned_by_domain(self.domain, is_active=True)},
        )

    def test_get_accessible(self):
        create_registry_for_test(self.user, self.domain, [Invitation('A')], name="reg1")
        create_registry_for_test(self.user, self.domain, [Invitation('A')], name="reg2")
        self.assertEqual(
            {"reg1", "reg2"},
            {reg.slug for reg in DataRegistry.objects.accessible_to_domain('A')}
        )
        # no invitation
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('B')))

    def test_get_accessible_inactive(self):
        registry = create_registry_for_test(self.user, self.domain, [Invitation('A')])
        registry.deactivate(self.user)
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('A')))

    def test_get_accessible_not_accepted(self):
        create_registry_for_test(self.user, self.domain, [Invitation('A', accepted=False)])
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('A')))

    def test_get_accessible_rejected(self):
        create_registry_for_test(self.user, self.domain, [Invitation('A', rejected=True)])
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('A')))

    def test_get_accessible_accepted_then_rejected(self):
        invitations = [
            Invitation('A', accepted=True, rejected=True),  # accepted and later rejected
        ]
        create_registry_for_test(self.user, self.domain, invitations)
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('A')))

    def test_get_accessible_slug(self):
        create_registry_for_test(self.user, self.domain, [Invitation('A')], name="reg1")
        create_registry_for_test(self.user, self.domain, [Invitation('A')], name="reg2")
        self.assertEqual(
            {"reg1"},
            {reg.slug for reg in DataRegistry.objects.accessible_to_domain('A', slug="reg1")}
        )

    def test_get_accessible_grants(self):
        invitations = [
            Invitation('A'),
            Invitation('B'),
        ]
        create_registry_for_test(self.user, self.domain, invitations, grants=[Grant("B", ["A"])], name="reg1")
        self.assertEqual(
            {"reg1"},
            {reg.slug for reg in DataRegistry.objects.accessible_to_domain('A', has_grants=True)}
        )
        # B has no grants
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('B', has_grants=True)))

    def test_get_accessible_grants_no_invite(self):
        create_registry_for_test(self.user, self.domain, grants=[Grant("B", ["A"])])
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain("A", has_grants=True)))

    def test_check_access(self):
        registry = create_registry_for_test(self.user, self.domain, [Invitation("A")])
        self.assertTrue(registry.check_access("A"))
        with self.assertRaises(RegistryAccessDenied):
            registry.check_access("B")

    def test_check_access_inactive(self):
        registry = create_registry_for_test(self.user, self.domain, [Invitation("A")])
        registry.deactivate(self.user)
        with self.assertRaises(RegistryAccessDenied):
            registry.check_access("A")

    def test_check_access_invite_not_accepted(self):
        registry = create_registry_for_test(self.user, self.domain, [Invitation("A", accepted=False)])
        with self.assertRaises(RegistryAccessDenied):
            registry.check_access("A")

    def test_check_access_invite_rejected(self):
        registry = create_registry_for_test(self.user, self.domain, [Invitation("A", rejected=True)])
        with self.assertRaises(RegistryAccessDenied):
            registry.check_access("A")

    def test_get_granted_domains(self):
        invitations = [Invitation('A'), Invitation('B'), Invitation('C')]
        grants = [
            Grant("A", ["B"]),
            Grant("B", ["A", "C"]),
            Grant("C", ["A"]),
        ]
        registry = create_registry_for_test(self.user, self.domain, invitations, grants, name="reg1")
        self.assertEqual({"A"}, registry.get_granted_domains("B"))
        self.assertEqual({"B", "C"}, registry.get_granted_domains("A"))
        self.assertEqual({"B"}, registry.get_granted_domains("C"))

    def test_visible_to_domain(self):
        invitations = [Invitation('A'), Invitation('B'), Invitation('C')]
        registries = [
            self.active,
            self.inactive,
            create_registry_for_test(self.user, self.domain, invitations),
            create_registry_for_test(self.user, "other", [Invitation(self.domain, accepted=False)]),
        ]
        visible = DataRegistry.objects.visible_to_domain(self.domain)
        self.assertEqual({r.name for r in registries}, {v.name for v in visible})
