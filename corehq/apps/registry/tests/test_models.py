from django.test import TestCase

from corehq.apps.registry.models import DataRegistry


class RegistryModelsTests(TestCase):
    domain = "registry-test"

    @classmethod
    def setUpTestData(cls):
        cls.active = DataRegistry.objects.create(domain=cls.domain, name="active registry")
        cls.inactive = DataRegistry.objects.create(domain=cls.domain, name="inactive registry", is_active=False)

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
