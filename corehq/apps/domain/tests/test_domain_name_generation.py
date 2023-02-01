from django.test import TestCase

from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.domain.models import Domain


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

    def test_conflict(self):
        name = "fandango"
        self.add_domain(name)
        self.assertEqual(Domain.generate_name(name), name + "-1")

    def test_failure(self):
        self.add_domain("ab")
        with self.assertRaises(NameUnavailableException):
            Domain.generate_name("abc", 2)

    def test_long_names(self):
        name = "abcd"

        self.add_domain(name)
        self.assertEqual(Domain.generate_name(name, 4), "ab-1")

        self.add_domain("ab-1")
        self.assertEqual(Domain.generate_name(name, 4), "ab-2")

        self.add_domain("ab-9")
        self.assertEqual(Domain.generate_name(name, 4), "a-1")

        self.add_domain("name")
        self.assertEqual(Domain.generate_name('very long name', 5), 'nam-1')
