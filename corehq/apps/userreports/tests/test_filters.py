from couchdbkit import Document
from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import FilterFactory
from corehq.apps.userreports.filters import PropertyMatchFilter
from fluff.filters import ANDFilter, ORFilter


class PropertyMatchFilterTest(SimpleTestCase):

    def setUp(self):
        self.filter = PropertyMatchFilter.from_spec({
            'property_name': 'foo',
            'property_value': 'bar',
        })
        self.assertEqual('foo', self.filter.property_name)
        self.assertEqual('bar', self.filter.property_value)

    def testNoName(self):
        self.assertRaises(BadSpecError, PropertyMatchFilter.from_spec, {
            'property_value': 'bar',
        })

    def testEmptyName(self):
        self.assertRaises(BadSpecError, PropertyMatchFilter.from_spec, {
            'property_name': '',
            'property_value': 'bar',
        })

    def testNoValue(self):
        self.assertRaises(BadSpecError, PropertyMatchFilter.from_spec, {
            'property_name': 'foo',
        })

    def testNoName(self):
        self.assertRaises(BadSpecError, PropertyMatchFilter.from_spec, {
            'property_name': 'foo',
            'property_value': '',
        })

    def testFilterMatch(self):
        self.assertTrue(self.filter.filter(Document(foo='bar')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(Document(foo='not bar')))

    def testFilterMissing(self):
        self.assertFalse(self.filter.filter(Document(not_foo='bar')))

    def testFromFactory(self):
        from_factory = FilterFactory.from_spec({
            'type': 'property_match',
            'property_name': 'foo',
            'property_value': 'bar',
        })
        self.assertTrue(isinstance(from_factory, PropertyMatchFilter))
        self.assertEqual('foo', from_factory.property_name)
        self.assertEqual('bar', from_factory.property_value)


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
        self.assertTrue(self.filter.filter(Document(foo='bar', foo2='bar2')))

    def testFilterPartialMatch(self):
        self.assertFalse(self.filter.filter(Document(foo='bar', foo2='not bar2')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(Document(foo='not bar', foo2='not bar2')))

    def testFilterMissingPartialMatch(self):
        self.assertFalse(self.filter.filter(Document(foo='bar')))

    def testFilterMissingAll(self):
        self.assertFalse(self.filter.filter(Document(notfoo='not bar')))

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
        self.assertTrue(self.filter.filter(Document(foo='bar', foo2='bar2')))

    def testFilterPartialMatch(self):
        self.assertTrue(self.filter.filter(Document(foo='bar', foo2='not bar2')))

    def testFilterNoMatch(self):
        self.assertFalse(self.filter.filter(Document(foo='not bar', foo2='not bar2')))

    def testFilterMissingPartialMatch(self):
        self.assertTrue(self.filter.filter(Document(foo='bar')))

    def testFilterMissingAll(self):
        self.assertFalse(self.filter.filter(Document(notfoo='not bar')))
