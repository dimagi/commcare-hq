from __future__ import print_function, unicode_literals

from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.models import Domain


class DomainNameAvailabilityTest(SimpleTestCase):
    def test_conflict(self):
        self.assertEquals(Domain._get_next_available_name("fandango", []), "fandango-1")


    def test_availability(self):
        name = "abc"
        similar = []

        self.assertEquals(Domain._get_next_available_name(name, similar), "abc-1")

        similar.append("abc-1");
        self.assertEquals(Domain._get_next_available_name(name, similar), "abc-2")

        # Don't bother filling in gaps
        similar.append("abc-9");
        self.assertEquals(Domain._get_next_available_name(name, similar), "abc-10")


class DomainNameGenerationTest(TestCase):
    def setUp(self):
        self.domains = []


    def add_domain(self, name):
        domain = Domain(name=name)
        domain.save()
        self.domains.append(domain)


    def tearDown(self):
        for domain in self.domains:
            domain.delete()


    def test_generation(self):
        self.assertEquals(Domain.generate_name("I have  spaces"), "i-have-spaces")


    def test_conflict(self):
        name = "fandango"
        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name), name + "-1")


    def test_failure(self):
        name = "ab"
        self.add_domain(name)
        with self.assertRaises(Exception):
            Domain.generate_name(name, 1)


    def test_long_names(self):
        name = "abcd"

        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name, 4), "ab-1")

        self.add_domain("ab-1")
        self.assertEquals(Domain.generate_name(name, 4), "ab-2")

        self.add_domain("ab-9")
        self.assertEquals(Domain.generate_name(name, 4), "a-1")
