from __future__ import absolute_import
from decimal import Decimal
import datetime
from django.test import SimpleTestCase

from ..xml_utils import serialize


class XMLSerializeTest(SimpleTestCase):

    def test_number_serialization(self):
        value = 1
        self.assertTrue(isinstance(value, int))
        self.assertEqual(serialize(value), '1')

        value = 0.004
        self.assertTrue(isinstance(value, float))
        self.assertEqual(serialize(value), '0.004')

        value = Decimal('100')
        self.assertTrue(isinstance(value, Decimal))
        self.assertEqual(serialize(value), '100')

    def test_string_serialization(self):
        self.assertEqual(serialize('ben'), 'ben')

    def test_none_serialization(self):
        self.assertEqual(serialize(None), '')

    def test_long_serialization(self):
        self.assertEqual(serialize(123), '123')

    def test_date_serialization(self):
        self.assertEqual(serialize(datetime.date(1982, 5, 14)), '1982-05-14')

    def test_datetime_serialization(self):
        self.assertEqual(serialize(datetime.datetime(2001, 1, 1, 12, 30, 45)), '2001-01-01T12:30:45.000000Z')

    def test_time_serialization(self):
        self.assertEqual(serialize(datetime.time(12, 4, 30)), '12:04:30')
