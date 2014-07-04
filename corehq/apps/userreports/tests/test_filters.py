from couchdbkit import Document
from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters import PropertyMatchFilter


class PropertyMatchFilterTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.filter = PropertyMatchFilter.from_spec({
            'property_name': 'foo',
            'property_value': 'bar',
        })

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
