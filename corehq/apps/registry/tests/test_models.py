from django.test import TestCase

from corehq.apps.registry.models import DataRegistry


class RegistryModelsTests(TestCase):
    domain = "registry-test"

    def test_slug_unique_per_domain(self):
        r1 = DataRegistry.objects.create(domain=self.domain, name="patient registry")
        r2 = DataRegistry.objects.create(domain=self.domain, name="the patient registry")
        r3 = DataRegistry.objects.create(domain="other_domain", name="the patient registry")
        self.assertEqual(r1.slug, "patient-registry")
        self.assertEqual(r2.slug, "patient-registry-2")
        self.assertEqual(r3.slug, "patient-registry")
