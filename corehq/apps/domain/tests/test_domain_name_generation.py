
from django.test import TestCase
from django.test.testcases import SimpleTestCase

from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import get_domain_url_slug
from corehq.util.test_utils import generate_cases


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
        self.assertEquals(Domain.generate_name(name), name + "-1")

    def test_failure(self):
        self.add_domain("ab")
        with self.assertRaises(NameUnavailableException):
            Domain.generate_name("abc", 2)

    def test_long_names(self):
        name = "abcd"

        self.add_domain(name)
        self.assertEquals(Domain.generate_name(name, 4), "ab-1")

        self.add_domain("ab-1")
        self.assertEquals(Domain.generate_name(name, 4), "ab-2")

        self.add_domain("ab-9")
        self.assertEquals(Domain.generate_name(name, 4), "a-1")

        self.add_domain("name")
        self.assertEqual(Domain.generate_name('very long name', 5), 'nam-1')


class DomainNameShorteningTest(SimpleTestCase):
    pass


@generate_cases([
    ('long name with stop words in it', 30, 'name-stop-words'),
    ('long name with stop words in it', 14, 'name-stop'),
], DomainNameShorteningTest)
def test_shorten_name(self, hr_name, max_length, expected):
    result = get_domain_url_slug(hr_name, max_length=max_length)
    self.assertEqual(result, expected)
