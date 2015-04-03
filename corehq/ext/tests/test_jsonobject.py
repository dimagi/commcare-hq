from django.test import SimpleTestCase
import jsonobject
from jsonobject.exceptions import BadValueError
from corehq.ext.jsonobject import TransitionalExactDateTimeProperty


class Foo(jsonobject.JsonObject):
    bar = TransitionalExactDateTimeProperty()


class TransitionalExactDateTimePropertyTest(SimpleTestCase):
    def test_wrap_old(self):
        foo = Foo.wrap({'bar': '2015-01-01T12:00:00Z'})
        self.assertEqual(foo.to_json()['bar'], '2015-01-01T12:00:00.000000Z')

    def test_wrap_new(self):
        foo = Foo.wrap({'bar': '2015-01-01T12:00:00.120054Z'})
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
