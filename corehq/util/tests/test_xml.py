from decimal import Decimal
from django.test import SimpleTestCase

from ..xml import serialize


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
        self.assertEqual(serialize(123L), '123')
