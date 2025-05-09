from datetime import datetime
from django.test import SimpleTestCase
import jsonobject
from jsonobject.exceptions import BadValueError
from dimagi.ext.jsonobject import DateTimeProperty, re_trans_datetime


class Foo(jsonobject.JsonObject):
    bar = DateTimeProperty()


class TransitionalExactDateTimePropertyTest(SimpleTestCase):
    def test_wrap_old(self):
        foo = Foo.wrap({'bar': '2015-01-01T12:00:00Z'})
        self.assertEqual(foo.bar, datetime(2015, 1, 1, 12, 0, 0, 0))
        self.assertEqual(foo.to_json()['bar'], '2015-01-01T12:00:00.000000Z')

    def test_wrap_new(self):
        foo = Foo.wrap({'bar': '2015-01-01T12:00:00.120054Z'})
        self.assertEqual(foo.bar, datetime(2015, 1, 1, 12, 0, 0, 120054))
        self.assertEqual(foo.to_json()['bar'], '2015-01-01T12:00:00.120054Z')

    def test_wrap_milliseconds_only(self):
        with self.assertRaises(BadValueError):
            Foo.wrap({'bar': '2015-01-01T12:00:00.120Z'})

    def test_wrap_old_no_Z(self):
        with self.assertRaises(BadValueError):
            Foo.wrap({'bar': '2015-01-01T12:00:00'})

    def test_wrap_new_no_Z(self):
        with self.assertRaises(BadValueError):
            Foo.wrap({'bar': '2015-01-01T12:00:00.120054'})


class TestDateRegex(SimpleTestCase):

    def test_strict_match(self):
        cases = [
            ('2015-01-01T12:00:00.120054Z', True),
            ('2015-10-01T14:05:45.087434Z', True),
            ('2015-04-03', False),
            ('2013-03-09T06:30:09.007', False),
            ('2013-03-09T06:30:09.007+03', False),
            ('351602061044374', False),
            ('2015-10-01T14:05:45Z', True),
        ]
        for candidate, expected in cases:
            self.assertEqual(bool(re_trans_datetime.match(candidate)), expected, candidate)


class DateTimePropertyTests(SimpleTestCase):
    def test_wrap(self):
        prop = DateTimeProperty()
        result = prop.wrap('2015-01-01T12:00:00.120054Z')
        self.assertEqual(result, datetime(year=2015, month=1, day=1, hour=12, microsecond=120054))

    def test_unwrap(self):
        prop = DateTimeProperty()
        (value, unwrapped) = prop.unwrap(datetime(year=2015, month=1, day=1, hour=12, microsecond=120054))
        self.assertEqual(value, datetime(year=2015, month=1, day=1, hour=12, microsecond=120054))
        self.assertEqual(unwrapped, '2015-01-01T12:00:00.120054Z')

    def test_deserialize(self):
        result = DateTimeProperty.deserialize('2015-01-01T12:00:00.120054Z')
        self.assertEqual(result, datetime(year=2015, month=1, day=1, hour=12, microsecond=120054))
