from __future__ import absolute_import
from django.test import SimpleTestCase

from custom.icds_reports.utils import indian_formatted_number


class TestIndiaNumberFormat(SimpleTestCase):

    def test_less_then_thousand(self):
        number = 900
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, "900")

    def test_thousands(self):
        number = 2000
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, "2,000")

    def test_hundred_of_thousands(self):
        number = 200000
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, "2,00,000")

    def test_milions(self):
        number = 10000000
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, "1,00,00,000")

    def test_if_parameter_will_be_numeric_string(self):
        number = "10000000"
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, "1,00,00,000")

    def test_wrong_data(self):
        number = "some non numeric value"
        india_format = indian_formatted_number(number)
        self.assertEquals(india_format, 0)
