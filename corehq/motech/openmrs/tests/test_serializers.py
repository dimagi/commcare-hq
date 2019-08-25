# coding=utf-8

import datetime
import doctest

from django.test import SimpleTestCase

import corehq.motech.openmrs.serializers
from corehq.motech.openmrs.serializers import to_omrs_date, to_omrs_datetime


class SerializerTests(SimpleTestCase):

    def test_to_timestamp_datetime(self):

        class CAT(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(hours=2)
            def tzname(self, dt):
                return "CAT"
            def dst(self, dt):
                return datetime.timedelta(0)

        dt = datetime.datetime(2017, 6, 27, 9, 36, 47, tzinfo=CAT())
        openmrs_datetime = to_omrs_datetime(dt)
        self.assertEqual(openmrs_datetime, '2017-06-27T09:36:47.000+0200')

    def test_to_timestamp_datetime_str(self):
        datetime_str = '2017-06-27T09:36:47.396000Z'
        openmrs_datetime = to_omrs_datetime(datetime_str)
        self.assertEqual(openmrs_datetime, '2017-06-27T09:36:47.396+0000')

    def test_to_timestamp_date(self):
        date = datetime.date(2017, 6, 27)
        openmrs_datetime = to_omrs_datetime(date)
        self.assertEqual(openmrs_datetime, '2017-06-27T00:00:00.000+0000')

    def test_to_timestamp_day_str(self):
        day_str = 'Wednesday'
        with self.assertRaisesMessage(ValueError, '"Wednesday" is not recognised as a date or a datetime'):
            to_omrs_datetime(day_str)

    def test_to_timestamp_day_num(self):
        day_str = '1'
        with self.assertRaisesMessage(ValueError, '"1" is not recognised as a date or a datetime'):
            to_omrs_datetime(day_str)

    def test_to_timestamp_int(self):
        day_int = 1
        openmrs_timestamp = to_omrs_datetime(day_int)
        self.assertIsNone(openmrs_timestamp)

    def test_to_date_datetime_str(self):
        datetime_str = '2017-06-27T09:36:47.396000Z'
        openmrs_date = to_omrs_date(datetime_str)
        self.assertEqual(openmrs_date, '2017-06-27')

    def test_to_date_int(self):
        day_int = 1
        openmrs_date = to_omrs_date(day_int)
        self.assertIsNone(openmrs_date)


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.serializers)
        self.assertEqual(results.failed, 0)
