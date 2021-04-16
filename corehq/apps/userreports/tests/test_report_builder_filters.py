from django.test import SimpleTestCase

from corehq.apps.userreports.reports.builder import const
from corehq.apps.userreports.reports.builder.filter_formats import get_pre_filter_format


class PreFilterFormatTest(SimpleTestCase):

    def test_empty_filter_format(self):
        self.assertEqual(const.PRE_FILTER_VALUE_IS_EMPTY, get_pre_filter_format({
            'pre_operator': '',
            'pre_value': '',
        }))

    def test_exists_filter_format(self):
        self.assertEqual(const.PRE_FILTER_VALUE_EXISTS, get_pre_filter_format({
            'pre_operator': '!=',
            'pre_value': '',
        }))

    def test_not_equal_filter_format(self):
        self.assertEqual(const.PRE_FILTER_VALUE_NOT_EQUAL, get_pre_filter_format({
            'pre_operator': 'distinct from',
            'pre_value': '',
        }))
        self.assertEqual(const.PRE_FILTER_VALUE_NOT_EQUAL, get_pre_filter_format({
            'pre_operator': 'distinct from',
            'pre_value': 'a_value',
        }))

    def test_value_filter_format(self):
        self.assertEqual(const.FORMAT_VALUE, get_pre_filter_format({
            'pre_operator': '=',
            'pre_value': 'a_value',
        }))

    def test_date_filter_format(self):
        # this is a bit weird but just documenting current behavior, which uses
        # the lack of value to assume it is a date
        self.assertEqual(const.FORMAT_DATE, get_pre_filter_format({
            'pre_operator': '=',
            'pre_value': '',
        }))
