import datetime

from django.test import SimpleTestCase

from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.case.util import validate_phone_datetime


class ValidatePhoneDatetimeTests(SimpleTestCase):

    def test_datetime_string(self):
        datetime_string = '2019-08-27T17:50:00.000'
        result = validate_phone_datetime(datetime_string)
        self.assertEqual(result, datetime.datetime(
            2019, 8, 27,
            17, 50, 0,
            tzinfo=datetime.timezone.utc
        ))

    def test_date_string(self):
        date_string = '2019-08-27'
        result = validate_phone_datetime(date_string)
        self.assertEqual(result, datetime.datetime(
            2019, 8, 27,
            0, 0, 0,
            tzinfo=datetime.timezone.utc
        ))

    def test_datetime(self):
        datetime_ = datetime.datetime(
            2019, 8, 27,
            17, 50, 0
        )
        result = validate_phone_datetime(datetime_)
        self.assertEqual(result, datetime_)

    def test_date(self):
        date = datetime.date(2019, 8, 27)
        result = validate_phone_datetime(date)
        self.assertEqual(result, datetime.datetime(
            2019, 8, 27,
            0, 0, 0
        ))

    def test_int(self):
        with self.assertRaises(PhoneDateValueError):
            validate_phone_datetime(1)

    def test_day_string(self):
        with self.assertRaises(PhoneDateValueError):
            validate_phone_datetime('Monday')

    def test_int_string(self):
        with self.assertRaises(PhoneDateValueError):
            validate_phone_datetime('1')
