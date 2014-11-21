from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.getters import DictGetter, NestedDictGetter, TransformedGetter
from corehq.apps.userreports.getters.factory import GetterFactory
from corehq.apps.userreports.getters.specs import PropertyNameMatchGetterSpec


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


class GetterFromSpecTest(SimpleTestCase):

    def test_invalid_type(self):
        with self.assertRaises(BadSpecError):
            GetterFactory.from_spec({
                'type': 'not_a_valid_type',
            })

    def test_property_name_match(self):
        getter = GetterFactory.from_spec({
            'type': 'property_name_match',
            'property_name': 'foo',
        })
        self.assertEqual(DictGetter, type(getter))
        self.assertEqual('foo', getter.property_name)

    def test_property_name_no_name(self):
        with self.assertRaises(BadSpecError):
            GetterFactory.from_spec({
                'type': 'property_name_match',
            })

    def test_property_name_empty_name(self):
        with self.assertRaises(BadSpecError):
            GetterFactory.from_spec({
                'type': 'property_name_match',
                'property_name': None,
            })

    def test_property_path_match(self):
        getter = GetterFactory.from_spec({
            'type': 'property_path_match',
            'property_path': ['path', 'to', 'foo'],
        })
        self.assertEqual(NestedDictGetter, type(getter))
        self.assertEqual(['path', 'to', 'foo'], getter.property_path)

    def test_property_path_no_path(self):
        with self.assertRaises(BadSpecError):
            GetterFactory.from_spec({
                'type': 'property_path_match',
            })

    def test_property_path_empty_path(self):
        for empty_path in ([], None):
            with self.assertRaises(BadSpecError):
                GetterFactory.from_spec({
                    'type': 'property_path_match',
                    'property_path': empty_path,
                })
