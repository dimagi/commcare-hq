from __future__ import print_function, unicode_literals

from django.test import TestCase

from corehq.apps.domain.models import Domain


class DomainNameGenerationTestBase(TestCase):
    def setUp(self):
        self.domains = []

    def add_domain(self, name):
        domain = Domain(name=name)
        domain.save()
        self.domains.append(domain)

    def tearDown(self):
        for domain in self.domains:
            domain.delete()


class DomainNameGenerationBasicTest(DomainNameGenerationTestBase):
    def test_generation(self):
        self.assertEquals(Domain.generate_name("I have  spaces"), "i-have-spaces")

    def test_conflict(self):
        name = "fandango"
        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name), name + "-1")

    def test_periods(self):
        name = "two.words"
        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name), "two-words-1")

    def test_failure(self):
        name = "ab"
        self.add_domain(name)
        self.assertFalse(Domain.generate_name(name, 1))

    def test_long_names(self):
        name = "abcd"

        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name, 4), "ab-1")

        self.add_domain("ab-1")
        self.assertEquals(Domain.generate_name(name, 4), "ab-2")

        self.add_domain("ab-9")
        self.assertEquals(Domain.generate_name(name, 4), "a-10")
