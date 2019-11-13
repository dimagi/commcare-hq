from datetime import date, datetime

from django.test import SimpleTestCase

from corehq.motech.serializers import to_date_str, to_integer


class SerializerTests(SimpleTestCase):

    def test_to_date_str_datetime(self):
        datetime_ = datetime(2017, 6, 27, 9, 36, 47)
        date_str = to_date_str(datetime_)
        self.assertEqual(date_str, '2017-06-27')

    def test_to_date_str_date(self):
        date_ = date(2017, 6, 27)
        date_str = to_date_str(date_)
        self.assertEqual(date_str, '2017-06-27')

    def test_to_date_str_datetime_str(self):
        datetime_str = '2017-06-27T09:36:47.396000Z'
        date_str = to_date_str(datetime_str)
        self.assertEqual(date_str, '2017-06-27')

    def test_to_date_str_int(self):
        day_int = 1
        date_str = to_date_str(day_int)
        self.assertIsNone(date_str)

    def test_to_integer_none(self):
        value = to_integer(None)
        self.assertIsNone(value)

    def test_to_integer_valid_str(self):
        value = to_integer("123")
        self.assertEqual(value, 123)

    def test_to_integer_invalid_str(self):
        value = to_integer("one hundred and twenty three")
        self.assertIsNone(value)

    def test_to_integer_float(self):
        value = to_integer(1.23)
        self.assertEqual(value, 1)
