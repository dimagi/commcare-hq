from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import FilterFactory
from fluff.filters import ANDFilter, ORFilter


class PropertyMatchFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = FilterFactory.from_spec({
            'type': 'property_match',
            'property_name': 'foo',
            'property_value': 'bar',
        })

    def testNoName(self):
        self.assertRaises(BadSpecError, FilterFactory.from_spec, {
            'type': 'property_match',
            'property_value': 'bar',
        })

    def testEmptyName(self):
        self.assertRaises(BadSpecError, FilterFactory.from_spec, {
            'type': 'property_match',
            'property_name': '',
            'property_value': 'bar',
        })

    def testNoValue(self):
        self.assertRaises(BadSpecError, FilterFactory.from_spec, {
            'type': 'property_match',
            'property_name': 'foo',
        })

    def testEmptyValue(self):
        self.assertRaises(BadSpecError, FilterFactory.from_spec, {
            'type': 'property_match',
            'property_name': 'foo',
            'property_value': '',
        })

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(dict(foo='bar')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(dict(foo='not bar')))

    def testFilterMissing(self):
        self.assertFalse(self.filter.filter(dict(not_foo='bar')))


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
