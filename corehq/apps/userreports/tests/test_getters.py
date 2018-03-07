from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.userreports.expressions.getters import DictGetter, NestedDictGetter, TransformedGetter


class Foo(object):
    # helper class used in tests

    @property
    def foo(self):
        return 'success'


class DictGetterTest(SimpleTestCase):

    def setUp(self):
        self.getter = DictGetter('foo')

    def test_basic(self):
        self.assertEqual('bar', self.getter({'foo': 'bar'}))

    def test_property_missing(self):
        self.assertEqual(None, self.getter({'not_foo': 'bar'}))

    def test_not_a_dict(self):
        self.assertEqual(None, self.getter(Foo()))

    def test_null(self):
        self.assertEqual(None, self.getter(None))


class NestedDictGetterTest(SimpleTestCase):

    def setUp(self):
        self.getter = NestedDictGetter(['path', 'to', 'foo'])

    def test_basic(self):
        self.assertEqual('bar', self.getter({
            'path': {
                'to': {
                    'foo': 'bar'
                }
            }
        }))

    def test_property_missing(self):
        self.assertEqual(None, self.getter({}))
        self.assertEqual(None, self.getter({'foo': 'bar'}))
        self.assertEqual(None, self.getter({
            'path': {
                'to': {
                    'not foo': 'bar'
                }
            }
        }))

    def test_not_a_dict(self):
        self.assertEqual(None, self.getter(Foo()))

    def test_null(self):
        self.assertEqual(None, self.getter(None))


class TransformedGetterTest(SimpleTestCase):

    def setUp(self):
        self.base_getter = DictGetter('foo')

    def test_no_transform(self):
        getter = TransformedGetter(self.base_getter, None)
        self.assertEqual('bar', getter({'foo': 'bar'}))
        self.assertEqual(1, getter({'foo': 1}))

    def test_basic(self):
        getter = TransformedGetter(self.base_getter, lambda x: '{}-transformed'.format(x))
        self.assertEqual('bar-transformed', getter({'foo': 'bar'}))
        self.assertEqual('1-transformed', getter({'foo': 1}))
