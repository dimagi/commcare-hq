from couchdbkit import Document
from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import IndicatorFactory


class BooleanIndicatorTest(SimpleTestCase):

    def setUp(self):
        self.indicator = IndicatorFactory.from_spec({
            'type': 'boolean',
            'column_id': 'col',
            'filter': {
                'type': 'property_match',
                'property_name': 'foo',
                'property_value': 'bar',
            }

        })
        self.assertEqual(1, len(self.indicator.get_columns()))

    def _check_result(self, indicator, document, value):
        [result] = indicator.get_values(document)
        self.assertEqual(value, result.value)


    def testNoColumnId(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'filter': {
                'type': 'property_match',
                'property_name': 'foo',
                'property_value': 'bar',
            }
        })

    def testEmptyColumnId(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'column_id': '',
            'filter': {
                'type': 'property_match',
                'property_name': 'foo',
                'property_value': 'bar',
            }
        })

    def testNoFilter(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'column_id': 'col',
        })

    def testEmptyFilter(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'column_id': 'col',
            'filter': None,
        })

    def testBadFilterType(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'column_id': 'col',
            'filter': 'wrong type',
        })

    def testInvalidFilter(self):
        self.assertRaises(BadSpecError, IndicatorFactory.from_spec, {
            'type': 'boolean',
            'column_id': 'col',
            'filter': {
                'type': 'property_match',
                'property_value': 'bar',
            }
        })

    def testIndicatorMatch(self):
        self._check_result(self.indicator, Document(foo='bar'), 1)

    def testIndicatorNoMatch(self):
        self._check_result(self.indicator, Document(foo='not bar'), 0)

    def testIndicatorMissing(self):
        self._check_result(self.indicator, Document(notfoo='bar'), 0)

    def testComplexStructure(self):
        # in slightly more compact format:
        # ((foo=bar) or (foo1=bar1 and foo2=bar2 and (foo3=bar3 or foo4=bar4)))
        indicator = IndicatorFactory.from_spec({
            "type": "boolean",
            "column_id": "col",
            "filter": {
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
            }
        })
        # first level or
        self._check_result(indicator, Document(foo='bar'), 1)
        # first level and with both or's
        self._check_result(indicator, Document(foo1='bar1', foo2='bar2', foo3='bar3'), 1)
        self._check_result(indicator, Document(foo1='bar1', foo2='bar2', foo4='bar4'), 1)

        # first and not right
        self._check_result(indicator, Document(foo1='not bar1', foo2='bar2', foo3='bar3'), 0)
        # second and not right
        self._check_result(indicator, Document(foo1='bar1', foo2='not bar2', foo3='bar3'), 0)
        # last and not right
        self._check_result(indicator, Document(foo1='bar1', foo2='bar2', foo3='not bar3', foo4='not bar4'), 0)
