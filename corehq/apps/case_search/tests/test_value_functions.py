from django.test import TestCase

from eulxml.xpath import parse as parse_xpath
from freezegun import freeze_time
from testil import eq

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.filter_dsl import FilterContext
from corehq.apps.case_search.xpath_functions.value_functions import today, date
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
        result = today(node, FilterContext("domain"))
        eq(result, '2021-08-02')

    def test_today_domain_tz(self):
        node = parse_xpath("today()")
        result = today(node, FilterContext(self.domain_name))
        eq(result, '2021-08-03')

    def test_arg_validation(self):
        node = parse_xpath("today('utc')")
        with self.assertRaises(XPathFunctionException):
            today(node, FilterContext("domain"))


@freeze_time('2021-08-02T22:00:00Z')
class TestDate(TestCase):
    def test_date_string(self):
        the_date = '2021-01-01'
        node = parse_xpath(f"date('{the_date}')")
        result = date(node, FilterContext("domain"))
        eq(result, the_date)

    def test_date_int(self):
        node = parse_xpath("date(15)")
        result = date(node, FilterContext("domain"))
        eq(result, '1970-01-16')

    def test_date_today(self):
        node = parse_xpath("date(today())")
        result = date(node, FilterContext("domain"))
        eq(result, '2021-08-02')
