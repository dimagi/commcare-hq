from django.test import TestCase

from eulxml.xpath import parse as parse_xpath
from freezegun import freeze_time
from testil import eq

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.xpath_functions.value_functions import today
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain


@freeze_time('2021-08-02T22:00:00Z')
class TestToday(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain_name = "test_today"
        cls.domain = create_domain(cls.domain_name)
        cls.domain.default_timezone = "Asia/Kolkata"
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        Domain.get_db().delete_doc(cls.domain)

    def test_today_no_domain(self):
        node = parse_xpath("today()")
        result = today("domain", node)
        eq(result, '2021-08-02')

    def test_today_domain_tz(self):
        node = parse_xpath("today()")
        result = today(self.domain_name, node)
        eq(result, '2021-08-03')

    def test_arg_validation(self):
        node = parse_xpath("today('utc')")
        with self.assertRaises(XPathFunctionException):
            today("domain", node)
