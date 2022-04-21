from django.test import TestCase

from eulxml.xpath import parse as parse_xpath
from freezegun import freeze_time
from testil import assert_raises, eq

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.filter_dsl import SearchFilterContext
from corehq.apps.case_search.xpath_functions.value_functions import (
    date,
    date_add,
    today,
)
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
        result = today(node, SearchFilterContext("domain"))
        eq(result, '2021-08-02')

    def test_today_domain_tz(self):
        node = parse_xpath("today()")
        result = today(node, SearchFilterContext(self.domain_name))
        eq(result, '2021-08-03')

    def test_arg_validation(self):
        node = parse_xpath("today('utc')")
        with self.assertRaises(XPathFunctionException):
            today(node, SearchFilterContext("domain"))


@freeze_time('2021-08-02T22:00:00Z')
class TestDate(TestCase):
    def test_date_string(self):
        the_date = '2021-01-01'
        node = parse_xpath(f"date('{the_date}')")
        result = date(node, SearchFilterContext("domain"))
        eq(result, the_date)

    def test_date_int(self):
        node = parse_xpath("date(15)")
        result = date(node, SearchFilterContext("domain"))
        eq(result, '1970-01-16')

    def test_date_today(self):
        node = parse_xpath("date(today())")
        result = date(node, SearchFilterContext("domain"))
        eq(result, '2021-08-02')


def test_date_add():
    def _do_test(expression, expected):
        node = parse_xpath(expression)
        result = date_add(node, SearchFilterContext("domain"))
        eq(result, expected)

    test_cases = [
        ("date-add('2020-02-29', 'years', 1)", "2021-02-28"),
        ("date-add('2020-02-29', 'years', 1.0)", "2021-02-28"),
        ("date-add('2022-01-01', 'months', 1)", "2022-02-01"),
        ("date-add('2022-01-01', 'months', '3')", "2022-04-01"),
        ("date-add('2020-04-30', 'months', -2)", "2020-02-29"),
        ("date-add('2020-03-31', 'weeks', 4)", "2020-04-28"),
        ("date-add('2020-02-01', 'weeks', 1.5)", "2020-02-11"),
        ("date-add('2022-01-01', 'days', -1)", "2021-12-31"),
        ("date-add('2022-01-01', 'days', 1.5)", "2022-01-02"),
        ("date-add('2022-01-01', 'days', '5')", "2022-01-06"),
        ("date-add(0, 'days', '5')", "1970-01-06"),
        ("date-add(365, 'years', '5')", "1976-01-01"),
        ("date-add(date('2021-01-01'), 'years', '5')", "2026-01-01"),
        ("date-add(date(5), 'months', '1')", "1970-02-06"),
    ]

    for expression, expected in test_cases:
        yield _do_test, expression, expected


def test_date_add_errors():
    def _do_test(expression):
        node = parse_xpath(expression)
        with assert_raises(XPathFunctionException):
            date_add(node, SearchFilterContext("domain"))

    test_cases = [
        # bad date
        "date-add('2020-02-31', 'years', 1)",
        "date-add(1.5, 'years', 1)",

        # non-integer quantity
        "date-add('2020-02-01', 'years', 1.5)",
        "date-add('2020-02-01', 'months', 1.5)",

        # non-numeric quantity
        "date-add('2020-02-01', 'months', 'five')",

        # bad interval names
        "date-add('2020-02-01', 'year', 1)",
        "date-add('2020-02-01', 'month', 1)",
        "date-add('2020-02-01', 'week', 1)",
        "date-add('2020-02-01', 'day', 1)",

        # missing args
        "date-add('2020-02-01', 'days')",
        "date-add('2020-02-01')",
        "date-add()",
    ]

    for expression in test_cases:
        yield _do_test, expression
