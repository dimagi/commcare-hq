from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import FilterFactory
from fluff.filters import ANDFilter, ORFilter, NOTFilter


class PropertyMatchFilterTest(SimpleTestCase):

    def get_filter(self):
        return FilterFactory.from_spec({
            'type': 'property_match',
            'property_name': 'foo',
            'property_value': 'bar',
        })

    def get_path_filter(self):
        return FilterFactory.from_spec({
            'type': 'property_match',
            'property_path': ['path', 'to', 'foo'],
            'property_value': 'bar',
        })

    def testNormalFilter(self):
        # just asserting that this doesn't raise any exceptions
        self.get_filter()

    def testFilterWithPath(self):
        # just asserting that this doesn't raise any exceptions
        self.get_path_filter()

    def testNoNameOrPath(self):
        with self.assertRaises(BadSpecError):
            FilterFactory.from_spec({
                'type': 'property_match',
                'property_value': 'bar',
            })

    def testEmptyName(self):
        with self.assertRaises(BadSpecError):
            FilterFactory.from_spec({
                'type': 'property_match',
                'property_name': '',
                'property_value': 'bar',
            })

    def testNameNoValue(self):
        with self.assertRaises(BadSpecError):
            FilterFactory.from_spec({
                'type': 'property_match',
                'property_name': 'foo',
            })

    def testEmptyPath(self):
        with self.assertRaises(BadSpecError):
            FilterFactory.from_spec({
                'type': 'property_match',
                'property_path': [],
                'property_value': 'bar',
            })

    def testFilterMatch(self):
        self.assertTrue(self.get_filter().filter(dict(foo='bar')))

    def testFilterNoMatch(self):
        self.assertFalse(self.get_filter().filter(dict(foo='not bar')))

    def testFilterMissing(self):
        self.assertFalse(self.get_filter().filter(dict(not_foo='bar')))

    def testFilterPathMatch(self):
        self.assertTrue(self.get_path_filter().filter({'path': {'to': {'foo': 'bar'}}}))

    def testFilterPathNoMatch(self):
        self.assertFalse(self.get_path_filter().filter({'path': {'to': {'foo': 'not bar'}}}))

    def testPathFilterMissing(self):
        self.assertFalse(self.get_path_filter().filter({'path': {'to': {'not_foo': 'bar'}}}))
        self.assertFalse(self.get_path_filter().filter({'foo': 'bar'}))


class EqualityFilterTest(PropertyMatchFilterTest):

    def get_filter(self):
        return FilterFactory.from_spec({
            'type': 'boolean_expression',
            'expression': {
                'type': 'property_name',
                'property_name': 'foo',
            },
            'operator': 'eq',
            'property_value': 'bar',
        })

    def get_path_filter(self):
        return FilterFactory.from_spec({
            'type': 'boolean_expression',
            'expression': {
                'type': 'property_path',
                'property_path': ['path', 'to', 'foo'],
            },
            'operator': 'eq',
            'property_value': 'bar',
        })


class BooleanExpressionFilterTest(SimpleTestCase):

    def get_filter(self, operator, value):
        return FilterFactory.from_spec({
            'type': 'boolean_expression',
            'expression': {
                'type': 'property_name',
                'property_name': 'foo',
            },
            'operator': operator,
            'property_value': value,
        })

    def test_equal(self):
        match = 'match'
        filter = self.get_filter('eq', match)
        self.assertTrue(filter.filter({'foo': match}))
        self.assertFalse(filter.filter({'foo': 'non-match'}))
        self.assertFalse(filter.filter({'foo': None}))

    def test_equal(self):
        match = 'match'
        filter = self.get_filter('not_eq', match)
        self.assertFalse(filter.filter({'foo': match}))
        self.assertTrue(filter.filter({'foo': 'non-match'}))
        self.assertTrue(filter.filter({'foo': None}))

    def test_in(self):
        values = ['a', 'b', 'c']
        filter = self.get_filter('in', values)
        for value in values:
            self.assertTrue(filter.filter({'foo': value}))
        for value in ['d', 'e', 'f']:
            self.assertFalse(filter.filter({'foo': value}))

    def test_in_multiselect(self):
        filter = self.get_filter('in_multi', 'a')
        self.assertTrue(filter.filter({'foo': 'a'}))
        self.assertTrue(filter.filter({'foo': 'a b c'}))
        self.assertTrue(filter.filter({'foo': 'b c a'}))
        self.assertFalse(filter.filter({'foo': 'b'}))
        self.assertFalse(filter.filter({'foo': 'abc'}))
        self.assertFalse(filter.filter({'foo': 'ab cd'}))
        self.assertFalse(filter.filter({'foo': 'd e f'}))

    def test_less_than(self):
        filter = self.get_filter('lt', 3)
        for match in (-10, 0, 2):
            self.assertTrue(filter.filter({'foo': match}))
        for non_match in (3, 11, '2'):
            self.assertFalse(filter.filter({'foo': non_match}))

    def test_less_than_equal(self):
        filter = self.get_filter('lte', 3)
        for match in (-10, 0, 2, 3):
            self.assertTrue(filter.filter({'foo': match}))
        for non_match in (4, 11, '2'):
            self.assertFalse(filter.filter({'foo': non_match}))

    def test_greater_than(self):
        filter = self.get_filter('gt', 3)
        for match in (4, 11, '2'):
            self.assertTrue(filter.filter({'foo': match}))
        for non_match in (-10, 0, 2, 3):
            self.assertFalse(filter.filter({'foo': non_match}))

    def test_greater_than_equal(self):
        filter = self.get_filter('gte', 3)
        for match in (3, 11, '2'):
            self.assertTrue(filter.filter({'foo': match}))
        for non_match in (-10, 0, 2):
            self.assertFalse(filter.filter({'foo': non_match}))


class ConfigurableANDFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = FilterFactory.from_spec({
            "type": "and",
            "filters": [
                {
                    "type": "property_match",
                    "property_name": "foo",
                    "property_value": "bar"
                },
                {
                    "type": "property_match",
                    "property_name": "foo2",
                    "property_value": "bar2"
                }
            ]
        })
        self.assertTrue(isinstance(self.filter, ANDFilter))

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='bar', foo2='bar2')))

    def testFilterPartialMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='bar', foo2='not bar2')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='not bar', foo2='not bar2')))

    def testFilterMissingPartialMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='bar')))

    def testFilterMissingAll(self):
        self.assertFalse(self.filter.filter(dict(notfoo='not bar')))


class ConfigurableORFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = FilterFactory.from_spec({
            "type": "or",
            "filters": [
                {
                    "type": "property_match",
                    "property_name": "foo",
                    "property_value": "bar"
                },
                {
                    "type": "property_match",
                    "property_name": "foo2",
                    "property_value": "bar2"
                }
            ]
        })
        self.assertTrue(isinstance(self.filter, ORFilter))

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='bar', foo2='bar2')))

    def testFilterPartialMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='bar', foo2='not bar2')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='not bar', foo2='not bar2')))

    def testFilterMissingPartialMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='bar')))

    def testFilterMissingAll(self):
        self.assertFalse(self.filter.filter(dict(notfoo='not bar')))


class ComplexFilterTest(SimpleTestCase):

    def testComplexStructure(self):
        # in slightly more compact format:
        # ((foo=bar) or (foo1=bar1 and foo2=bar2 and (foo3=bar3 or foo4=bar4)))
        filter = FilterFactory.from_spec({
            "type": "or",
            "filters": [
                {
                    "type": "property_match",
                    "property_name": "foo",
                    "property_value": "bar"
                },
                {
                    "type": "and",
                    "filters": [
                        {
                            "type": "property_match",
                            "property_name": "foo1",
                            "property_value": "bar1"
                        },
                        {
                            "type": "property_match",
                            "property_name": "foo2",
                            "property_value": "bar2"
                        },
                        {
                            "type": "or",
                            "filters": [
                                {
                                    "type": "property_match",
                                    "property_name": "foo3",
                                    "property_value": "bar3"
                                },
                                {
                                    "type": "property_match",
                                    "property_name": "foo4",
                                    "property_value": "bar4"
                                }
                            ]
                        },
                    ]
                },
            ]
        })
        # first level or
        self.assertTrue(filter.filter(dict(foo='bar')))
        # first level and with both or's
        self.assertTrue(filter.filter(dict(foo1='bar1', foo2='bar2', foo3='bar3')))
        self.assertTrue(filter.filter(dict(foo1='bar1', foo2='bar2', foo4='bar4')))

        # first and not right
        self.assertFalse(filter.filter(dict(foo1='not bar1', foo2='bar2', foo3='bar3')))
        # second and not right
        self.assertFalse(filter.filter(dict(foo1='bar1', foo2='not bar2', foo3='bar3')))
        # last and not right
        self.assertFalse(filter.filter(dict(foo1='bar1', foo2='bar2', foo3='not bar3', foo4='not bar4')))


class ConfigurableNOTFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = FilterFactory.from_spec({
            "type": "not",
            "filter": {
                "type": "property_match",
                "property_name": "foo",
                "property_value": "bar"
            }
        })
        self.assertTrue(isinstance(self.filter, NOTFilter))

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='not bar')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='bar')))


class ConfigurableNamedFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = FilterFactory.from_spec(
            {'type': 'named', 'name': 'foo'},
            {
                'foo': FilterFactory.from_spec({
                    "type": "not",
                    "filter": {
                        "type": "property_match",
                        "property_name": "foo",
                        "property_value": "bar"
                    }
                })
            }
        )
        self.assertTrue(isinstance(self.filter, NOTFilter))

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='not bar')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='bar')))
