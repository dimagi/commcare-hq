from __future__ import absolute_import
from __future__ import unicode_literals

from copy import copy
from datetime import datetime, date
from decimal import Decimal
import uuid

from django.test import SimpleTestCase, TestCase
from mock import patch

from casexml.apps.case.tests.util import delete_all_ledgers, delete_all_xforms
from casexml.apps.stock.const import REPORT_TYPE_BALANCE
from casexml.apps.stock.models import StockReport, StockTransaction

from corehq.apps.commtrack.processing import StockProcessingResult
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.userreports.indicators.utils import get_values_by_product
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.ledgers.helpers import StockReportHelper, StockTransactionHelper
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import get_simple_wrapped_form
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.utils.xform import TestFormMetadata


class SingleIndicatorTestBase(SimpleTestCase):

    def _check_result(self, indicator, document, value, context=None):
        [result] = indicator.get_values(document, context=context)
        self.assertEqual(value, result.value)


class BooleanIndicatorTest(SingleIndicatorTestBase):
    indicator_type = 'boolean'

    def setUp(self):
        self.indicator = IndicatorFactory.from_spec({
            'type': self.indicator_type,
            'column_id': 'col',
            'filter': {
                'type': 'property_match',
                'property_name': 'foo',
                'property_value': 'bar',
            }

        })
        self.assertEqual(1, len(self.indicator.get_columns()))

    def testNoColumnId(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
                'filter': {
                    'type': 'property_match',
                    'property_name': 'foo',
                    'property_value': 'bar',
                }
            })

    def testEmptyColumnId(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
                'column_id': '',
                'filter': {
                    'type': 'property_match',
                    'property_name': 'foo',
                    'property_value': 'bar',
                }
            })

    def testNoFilter(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
                'column_id': 'col',
            })

    def testEmptyFilter(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
                'column_id': 'col',
                'filter': None,
            })

    def testBadFilterType(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
                'column_id': 'col',
                'filter': 'wrong type',
            })

    def testInvalidFilter(self):
        with self.assertRaises(BadSpecError):
            IndicatorFactory.from_spec({
                'type': self.indicator_type,
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
            "type": self.indicator_type,
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

    def test_not_null_filter_root_doc(self):
        indicator = IndicatorFactory.from_spec(
            {
                "filter": {
                    "filter": {
                        "operator": "in",
                        "expression": {
                            "expression": {
                                "datatype": None,
                                "type": "property_name",
                                "property_name": "ccs_opened_date"
                            },
                            "type": "root_doc"
                        },
                        "type": "boolean_expression",
                        "property_value": [
                            "",
                            None
                        ]
                    },
                    "type": "not"
                },
                "type": self.indicator_type,
                "display_name": None,
                "column_id": "prop1_not_null"
            }
        )
        self._check_result(indicator, {}, 1, EvaluationContext(root_doc=dict(ccs_opened_date='not_null')))
        self._check_result(indicator, {}, 1, EvaluationContext(root_doc=dict(ccs_opened_date=' ')))
        self._check_result(indicator, {}, 0, EvaluationContext(root_doc=dict(ccs_opened_date='')))
        self._check_result(indicator, {}, 0, EvaluationContext(root_doc=dict(ccs_opened_date=None)))
        self._check_result(indicator, {}, 0, EvaluationContext(root_doc=dict()))


class SmallBooleanIndicatorTest(BooleanIndicatorTest):
    indicator_type = 'small_boolean'


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

    def test_raw_ints(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "integer",
            'property_name': 'foo',
            "display_name": "raw foos",
        })
        self._check_result(indicator, dict(foo="bar"), None)
        self._check_result(indicator, dict(foo=1), 1)
        self._check_result(indicator, dict(foo=1.2), 1)
        self._check_result(indicator, dict(foo=None), None)
        self._check_result(indicator, dict(nofoo='foryou'), None)

    def test_raw_small_ints(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "small_integer",
            'property_name': 'foo',
            "display_name": "raw foos",
        })
        self._check_result(indicator, dict(foo="bar"), None)
        self._check_result(indicator, dict(foo=1), 1)
        self._check_result(indicator, dict(foo=1.2), 1)
        self._check_result(indicator, dict(foo=None), None)
        self._check_result(indicator, dict(nofoo='foryou'), None)

    def test_raw_strings(self):
        indicator = IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "string",
            'property_name': 'foo',
            "display_name": "raw foos",
        })
        self._check_result(indicator, dict(foo="bar"), 'bar')
        self._check_result(indicator, dict(foo=1), '1')
        self._check_result(indicator, dict(foo=1.2), '1.2')
        self._check_result(indicator, dict(foo=None), None)
        self._check_result(indicator, dict(nofoo='foryou'), None)

    def testNestedSinglePath(self):
        self._check_result(
            self._default_nested_indicator(['property']),
            {'property': 'the right value'},
            'the right value'
        )

    def testNestedDeepReference(self):
        test_doc = {
            'parent': {
                'child': {
                    'grandchild': 'the right value'
                }
            }
        }
        self._check_result(
            self._default_nested_indicator(["parent", "child", "grandchild"]),
            test_doc,
            'the right value'
        )

    def testNestedInvalidTopLevel(self):
        self._check_result(
            self._default_nested_indicator(['parent', 'child']),
            {'badparent': 'bad value'},
            None,
        )

    def testNestedInvalidMidLevel(self):
        test_doc = {
            'parent': {
                'badchild': {
                    'grandchild': 'the wrong value'
                }
            }
        }
        self._check_result(
            self._default_nested_indicator(["parent", "child", "grandchild"]),
            test_doc,
            None
        )

    def _default_nested_indicator(self, path):
        return IndicatorFactory.from_spec({
            "type": "raw",
            "column_id": "foo",
            "datatype": "string",
            "property_path": path,
            "display_name": "indexed",
        })


class ExpressionIndicatorTest(SingleIndicatorTestBase):

    @property
    def simple_indicator(self):
        return IndicatorFactory.from_spec({
            "type": "expression",
            "expression": {
                "type": "property_name",
                "property_name": "foo",
            },
            "column_id": "foo",
            "datatype": "string",
            "display_name": "expression foos",
        })

    @property
    def complex_indicator(self):
        # this expression is the equivalent to:
        #   doc.true_value if doc.test == 'match' else doc.false_value
        return IndicatorFactory.from_spec({
            "type": "expression",
            "expression": {
                'type': 'conditional',
                'test': {
                    'type': 'boolean_expression',
                    'expression': {
                        'type': 'property_name',
                        'property_name': 'test',
                    },
                    'operator': 'eq',
                    'property_value': 'match',
                },
                'expression_if_true': {
                    'type': 'property_name',
                    'property_name': 'true_value',
                },
                'expression_if_false': {
                    'type': 'property_name',
                    'property_name': 'false_value',
                },
            },
            "column_id": "foo",
            "datatype": "string",
            "display_name": "expression foos",
        })

    def test_expression(self):
        self._check_result(self.simple_indicator, dict(foo="bar"), "bar")

    def test_missing_value(self):
        self._check_result(self.simple_indicator, dict(notfoo="bar"), None)

    def test_complicated_expression(self):
        # largely duplicated from ConditionalExpressionTest
        indicator = self.complex_indicator
        self._check_result(indicator, {
            'test': 'match',
            'true_value': 'correct',
            'false_value': 'incorrect',
        }, 'correct')
        self._check_result(indicator, {
            'test': 'non-match',
            'true_value': 'correct',
            'false_value': 'incorrect',
        }, 'incorrect')
        self._check_result(indicator, {
            'true_value': 'correct',
            'false_value': 'incorrect',
        }, 'incorrect')
        self._check_result(indicator, {}, None)

    def test_datasource_transform(self):
        indicator = IndicatorFactory.from_spec({
            "type": "expression",
            "column_id": "transformed_value",
            "display_name": "transformed value",
            "expression": {
                "type": "property_name",
                "property_name": "month",
            },
            "datatype": "string",
            "transform": {
                "type": "custom",
                "custom_type": "month_display"
            },
        })
        self._check_result(indicator, {'month': "3"}, "March")

    def test_literal(self):
        indicator = IndicatorFactory.from_spec({
            "type": "expression",
            "expression": 10,
            "column_id": "foo",
            "datatype": "integer"
        })
        self._check_result(indicator, {}, 10)
        self._check_result(indicator, {'foo': 'bar'}, 10)
        indicator = IndicatorFactory.from_spec({
            "type": "expression",
            "expression": 10,
            "column_id": "foo",
            "datatype": "small_integer"
        })
        self._check_result(indicator, {}, 10)
        self._check_result(indicator, {'foo': 'bar'}, 10)


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

    def testChoiceListWithPath(self):
        spec = copy(self.spec)
        del spec['property_name']
        spec['property_path'] = ['path', 'to', 'category']
        indicator = IndicatorFactory.from_spec(spec)
        self._check_vals(indicator, {'category': 'bug'}, [0, 0, 0, 0])
        self._check_vals(indicator, {'path': {'category': 'bug'}}, [0, 0, 0, 0])
        self._check_vals(indicator, {'path': {'to': {'category': 'bug'}}}, [1, 0, 0, 0])
        self._check_vals(indicator, {'path': {'to': {'nothing': 'bug'}}}, [0, 0, 0, 0])

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


class IndicatorDatatypeTest(SingleIndicatorTestBase):

    def testDecimal(self):
        indicator = IndicatorFactory.from_spec({
            'type': 'raw',
            'column_id': 'col',
            "property_name": "foo",
            "datatype": "decimal",
        })
        self._check_result(indicator, dict(foo=5.5), Decimal(5.5))
        self._check_result(indicator, dict(foo=None), None)
        self._check_result(indicator, dict(foo="banana"), None)


class LedgerBalancesIndicatorTest(SimpleTestCase):

    def setUp(self):
        self.spec = {
            "type": "ledger_balances",
            "column_id": "soh",
            "display_name": "Stock On Hand",
            "ledger_section": "soh",
            "product_codes": ["abc", "def", "ghi"],
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }
        self.stock_states = {'abc': 32, 'def': 85, 'ghi': 11}

    def test_ledger_balances_indicator(self):
        indicator = IndicatorFactory.from_spec(self.spec)
        doc = {'_id': 'case1', 'domain': 'domain'}

        with patch('corehq.apps.userreports.indicators.get_values_by_product', return_value=self.stock_states):
            values = indicator.get_values(doc, EvaluationContext(doc, 0))

        self.assertEqual(
            [(val.column.id, val.value) for val in values],
            [('soh_abc', 32), ('soh_def', 85), ('soh_ghi', 11)]
        )


class DueListDateIndicatorTest(SimpleTestCase):

    def setUp(self):
        self.spec = {
            "type": "due_list_date",
            "column_id": "immun_dates",
            "display_name": "Immunization date",
            "ledger_section": "immuns",
            "product_codes": ["tt_1", "tt_2", "hpv"],
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }
        self.stock_states = {'tt_1': 17000, 'tt_2': 17020, 'hpv': 18000}

    def test_ledger_balances_indicator(self):
        indicator = IndicatorFactory.from_spec(self.spec)
        doc = {'_id': 'case1', 'domain': 'domain'}

        with patch('corehq.apps.userreports.indicators.get_values_by_product', return_value=self.stock_states):
            values = indicator.get_values(doc, EvaluationContext(doc, 0))

        self.assertEqual(
            [(val.column.id, val.value) for val in values],
            [
                ('immun_dates_tt_1', date(2016, 7, 18)),
                ('immun_dates_tt_2', date(2016, 8, 7)),
                ('immun_dates_hpv', date(2019, 4, 14))
            ]
        )


class TestGetValuesByProduct(TestCase):
    domain_name = 'test-domain'
    case_id = 'case1'

    def create_report(self, transactions=None, tag=None, date=None):
        form = get_simple_wrapped_form(uuid.uuid4().hex, metadata=TestFormMetadata(domain=self.domain_name))
        report = StockReportHelper.make_from_form(
            form,
            date or datetime.utcnow(),
            tag or REPORT_TYPE_BALANCE,
            transactions or [],
        )
        return report, form

    def _create_models_for_stock_report_helper(self, form, stock_report_helper):
        processing_result = StockProcessingResult(form, stock_report_helpers=[stock_report_helper])
        processing_result.populate_models()
        if should_use_sql_backend(self.domain_name):
            from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
            LedgerAccessorSQL.save_ledger_values(processing_result.models_to_save)
        else:
            processing_result.commit()

    @classmethod
    def setUpClass(cls):
        super(TestGetValuesByProduct, cls).setUpClass()
        cls.data = [
            {"product_id": uuid.uuid4().hex, "product": "coke", "section": "soh", "balance": 32},
            {"product_id": uuid.uuid4().hex, "product": "coke", "section": "consumption", "balance": 63},
            {"product_id": uuid.uuid4().hex, "product": "surge", "section": "soh", "balance": 85},
            {"product_id": uuid.uuid4().hex, "product": "fanta", "section": "soh", "balance": 11},
        ]

    @classmethod
    def tearDownClass(cls):
        SQLProduct.objects.all().delete()
        super(TestGetValuesByProduct, cls).tearDownClass()

    def setUp(self):
        super(TestGetValuesByProduct, self).setUp()
        self.ledger_processor = FormProcessorInterface(domain=self.domain_name).ledger_processor
        self.domain_obj = create_domain(self.domain_name)
        SQLProduct.objects.bulk_create([
            SQLProduct(domain=self.domain_name, product_id=data['product_id'], code=data['product'])
            for data in self.data
        ])

        transactions_flat = []
        self.transactions = {}
        for d in self.data:
            product = d['product']
            product_id = d['product_id']
            section = d['section']
            balance = d['balance']
            transactions_flat.append(
                StockTransactionHelper(
                    case_id=self.case_id,
                    section_id=section,
                    product_id=product_id,
                    action='soh',
                    quantity=balance,
                    timestamp=datetime.utcnow()
                )
            )
            self.transactions.setdefault(self.case_id, {}).setdefault(section, {})[product] = balance

        self.new_stock_report, self.form = self.create_report(transactions_flat)
        self._create_models_for_stock_report_helper(self.form, self.new_stock_report)

    def tearDown(self):
        self.domain_obj.delete()
        delete_all_xforms()
        delete_all_ledgers()
        StockReport.objects.all().delete()
        StockTransaction.objects.all().delete()
        super(TestGetValuesByProduct, self).tearDown()

    @run_with_all_backends
    def test_get_soh_values_by_product(self):
        values = get_values_by_product(
            self.domain_name, self.case_id, 'soh', ['coke', 'surge', 'new_coke']
        )
        self.assertEqual(values['coke'], 32)
        self.assertEqual(values['surge'], 85)
        self.assertEqual(values['new_coke'], 0)

    @run_with_all_backends
    def test_get_consumption_by_product(self):
        values = get_values_by_product(
            self.domain_name, self.case_id, 'consumption', ['coke', 'surge', 'new_coke']
        )
        self.assertEqual(values['coke'], 63)
        self.assertEqual(values['surge'], 0)
        self.assertEqual(values['new_coke'], 0)
