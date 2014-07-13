from copy import copy
from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import IndicatorFactory


class SingleIndicatorTestBase(SimpleTestCase):

    def _check_result(self, indicator, document, value):
        [result] = indicator.get_values(document)
        self.assertEqual(value, result.value)



class BooleanIndicatorTest(SingleIndicatorTestBase):

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
        self._check_result(self.indicator, dict(foo='bar'), 1)

    def testIndicatorNoMatch(self):
        self._check_result(self.indicator, dict(foo='not bar'), 0)

    def testIndicatorMissing(self):
        self._check_result(self.indicator, dict(notfoo='bar'), 0)

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
        self._check_result(indicator, dict(foo='bar'), 1)
        # first level and with both or's
        self._check_result(indicator, dict(foo1='bar1', foo2='bar2', foo3='bar3'), 1)
        self._check_result(indicator, dict(foo1='bar1', foo2='bar2', foo4='bar4'), 1)

        # first and not right
        self._check_result(indicator, dict(foo1='not bar1', foo2='bar2', foo3='bar3'), 0)
        # second and not right
        self._check_result(indicator, dict(foo1='bar1', foo2='not bar2', foo3='bar3'), 0)
        # last and not right
        self._check_result(indicator, dict(foo1='bar1', foo2='bar2', foo3='not bar3', foo4='not bar4'), 0)


class CountIndicatorTest(SingleIndicatorTestBase):
    def testCount(self):
        indicator = IndicatorFactory.from_spec({
            "type": "count",
            "column_id": "count",
            "display_name": "Count"
        })
        self._check_result(indicator, dict(), 1)


class RawIndicatorTest(SingleIndicatorTestBase):

    def testMetadataDefaults(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "integer",
            'property_name': 'foo',
            "display_name": "raw foos",
        })
        self.assertEqual(True, indicator.column.is_nullable)
        self.assertEqual(False, indicator.column.is_primary_key)

    def testMetadataOverrides(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "integer",
            'property_name': 'foo',
            "display_name": "raw foos",
            "is_nullable": False,
            "is_primary_key": True,
        })
        self.assertEqual(False, indicator.column.is_nullable)
        self.assertEqual(True, indicator.column.is_primary_key)

    def testRaw(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "integer",
            'property_name': 'foo',
            "display_name": "raw foos",
        })
        # todo: eventually data types should be smarter than this.
        # when this test starts failing that will be a good thing and when we should fix it.
        self._check_result(indicator, dict(foo="bar"), "bar")
        self._check_result(indicator, dict(foo=1), 1)
        self._check_result(indicator, dict(foo=1.2), 1.2)
        self._check_result(indicator, dict(foo=None), None)
        self._check_result(indicator, dict(nofoo='foryou'), None)


class ChoiceListIndicatorTest(SimpleTestCase):
    def setUp(self):
        self.spec = {
            "type": "choice_list",
            "column_id": "col",
            "display_name": "the category",
            "property_name": "category",
            "choices": [
                "bug",
                "feature",
                "app",
                "schedule"
            ],
            "select_style": "single",
        }

    def _check_vals(self, indicator, document, expected_values):
        values = indicator.get_values(document)
        for i, val in enumerate(values):
            self.assertEqual(expected_values[i], val.value)

    def testConstructChoiceList(self):
        indicator = IndicatorFactory.from_spec(self.spec)
        cols = indicator.get_columns()
        self.assertEqual(4, len(cols))
        for i, choice in enumerate(self.spec['choices']):
            self.assertTrue(self.spec['column_id'] in cols[i].id)
            self.assertTrue(choice in cols[i].id)

        self.assertEqual(self.spec['display_name'], indicator.display_name)

    def testSingleSelectIndicators(self):
        indicator = IndicatorFactory.from_spec(self.spec)
        self._check_vals(indicator, dict(category='bug'), [1, 0, 0, 0])
        self._check_vals(indicator, dict(category='feature'), [0, 1, 0, 0])
        self._check_vals(indicator, dict(category='app'), [0, 0, 1, 0])
        self._check_vals(indicator, dict(category='schedule'), [0, 0, 0, 1])
        self._check_vals(indicator, dict(category='nomatch'), [0, 0, 0, 0])
        self._check_vals(indicator, dict(category=''), [0, 0, 0, 0])
        self._check_vals(indicator, dict(nocategory='bug'), [0, 0, 0, 0])

    def testMultiSelectIndicators(self):
        spec = copy(self.spec)
        spec['select_style'] = 'multiple'
        indicator = IndicatorFactory.from_spec(spec)
        self._check_vals(indicator, dict(category='bug'), [1, 0, 0, 0])
        self._check_vals(indicator, dict(category='feature'), [0, 1, 0, 0])
        self._check_vals(indicator, dict(category='app'), [0, 0, 1, 0])
        self._check_vals(indicator, dict(category='schedule'), [0, 0, 0, 1])
        self._check_vals(indicator, dict(category='nomatch'), [0, 0, 0, 0])
        self._check_vals(indicator, dict(category=''), [0, 0, 0, 0])
        self._check_vals(indicator, dict(nocategory='bug'), [0, 0, 0, 0])
        self._check_vals(indicator, dict(category='bug feature'), [1, 1, 0, 0])
        self._check_vals(indicator, dict(category='bug feature app schedule'), [1, 1, 1, 1])
        self._check_vals(indicator, dict(category='bug nomatch'), [1, 0, 0, 0])
