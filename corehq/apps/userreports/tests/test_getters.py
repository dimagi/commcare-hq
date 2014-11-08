from django.test import SimpleTestCase
from corehq.apps.userreports.getters import SimpleGetter, DictGetter, NestedDictGetter


class Foo(object):
    # helper class used in tests
    @property
    def foo(self):
        return 'success'


class SimpleGetterTest(SimpleTestCase):

    def setUp(self):
        self.getter = SimpleGetter('foo')

    def test_property(self):
        self.assertEqual('success', self.getter(Foo()))

    def test_property_missing(self):
        class NotFoo(object):
            pass

        self.assertEqual(None, self.getter(NotFoo()))

    def test_null(self):
        self.assertEqual(None, self.getter(None))


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
