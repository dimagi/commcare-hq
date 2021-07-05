from django.test import TestCase

from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.tests.utils import Invitation, create_registry_for_test


class RegistryModelsTests(TestCase):
    domain = "registry-test"

    @classmethod
    def setUpTestData(cls):
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
        invitations = [
            Invitation('A'),
            Invitation('B', accepted=False),
            Invitation('C', accepted=True, rejected=True),  # accepted and later rejected
        ]
        create_registry_for_test(self.domain, invitations, name="reg1")
        create_registry_for_test(self.domain, invitations, name="reg2")
        self.assertEqual(
            {"reg1", "reg2"},
            {reg.slug for reg in DataRegistry.objects.accessible_to_domain('A')}
        )
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('B')))
        self.assertEqual(0, len(DataRegistry.objects.accessible_to_domain('C')))
