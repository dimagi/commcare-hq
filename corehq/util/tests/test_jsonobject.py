import datetime
from django.test import SimpleTestCase
from jsonobject import JsonObject as TheirJsonObject
from dimagi.ext.jsonobject import JsonObject as OurJsonObject, re_trans_datetime
from jsonobject.exceptions import BadValueError


class JsonObjectTest(SimpleTestCase):

    JsonObject = TheirJsonObject

    def test_ms(self):
        class Foo(self.JsonObject):
            pass
        foo = Foo({'date': '2015-10-01T14:05:45.087434Z'})
        self.assertEqual(foo.date, datetime.datetime(2015, 10, 1, 14, 5, 45))

    def test_no_ms(self):
        class Foo(self.JsonObject):
            pass
        foo = Foo({'date': '2015-10-01T14:05:45Z'})
        self.assertEqual(foo.date, datetime.datetime(2015, 10, 1, 14, 5, 45))

    def test_dt(self):
        class Foo(self.JsonObject):
            pass
        with self.assertRaises(BadValueError):
            Foo({'date': datetime.datetime(2015, 10, 1, 14, 5, 45, 87434)})


class OurJsonObjectTest(JsonObjectTest):
    JsonObject = OurJsonObject

    def test_match(self):
        self.assertTrue(re_trans_datetime.match('2015-10-01T14:05:45.087434Z'), True)

    def test_ms(self):
        class Foo(self.JsonObject):
            pass
        foo = Foo({'date': '2015-10-01T14:05:45.087434Z'})
        self.assertEqual(foo.date, datetime.datetime(2015, 10, 1, 14, 5, 45, 87434))
