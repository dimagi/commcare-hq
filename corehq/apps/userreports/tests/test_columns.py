from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from sqlagg import SumWhen
from django.test import SimpleTestCase, TestCase

from casexml.apps.case.util import post_case_blocks
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.columns import get_distinct_values
from corehq.apps.userreports.const import DEFAULT_MAXIMUM_EXPANSION
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.reports.factory import ReportColumnFactory
from corehq.apps.userreports.reports.specs import FieldColumn, PercentageColumn, AggregateDateColumn
from corehq.apps.userreports.sql.columns import expand_column
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager, UCR_ENGINE_ID

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from six.moves import range


class TestFieldColumn(SimpleTestCase):

    def testColumnSetFromAlias(self):
        field = ReportColumnFactory.from_spec({
            "aggregation": "simple",
            "field": "doc_id",
            "alias": "the_right_answer",
            "type": "field",
        }, is_static=False)
        self.assertTrue(isinstance(field, FieldColumn))
        self.assertEqual('the_right_answer', field.column_id)

    def testColumnDefaultsToField(self):
        field = ReportColumnFactory.from_spec({
            "aggregation": "simple",
            "field": "doc_id",
            "type": "field",
        }, is_static=False)
        self.assertEqual('doc_id', field.column_id)

    def testBadAggregation(self):
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                "aggregation": "simple_",
                "field": "doc_id",
                "type": "field",
            }, is_static=False)

    def testGoodFormat(self):
        for format in [
            'default',
            'percent_of_total',
        ]:
            self.assertEquals(FieldColumn, type(
                ReportColumnFactory.from_spec({
                    "aggregation": "simple",
                    "field": "doc_id",
                    "format": format,
                    "type": "field",
                }, is_static=False)
            ))

    def testBadFormat(self):
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                "aggregation": "simple",
                "field": "doc_id",
                "format": "default_",
                "type": "field",
            }, is_static=False)


class ChoiceListColumnDbTest(TestCase):

    def test_column_uniqueness_when_truncated(self):
        problem_spec = {
            "display_name": "practicing_lessons",
            "property_name": "long_column",
            "choices": [
                # test for regression:
                # with sqlalchemy paramstyle='pyformat' (default)
                # some queries that included columns with ')' in the column name
                # would fail with a very cryptic message
                "duplicate_choice_1(s)",
                "duplicate_choice_2",
            ],
            "select_style": "multiple",
            "column_id": "a_very_long_base_selection_column_name_with_limited_room",
            "type": "choice_list",
        }
        data_source_config = DataSourceConfiguration(
            domain='test',
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=uuid.uuid4().hex,
            configured_filter={},
            configured_indicators=[problem_spec],
        )
        adapter = get_indicator_adapter(data_source_config)
        adapter.rebuild_table()
        # ensure we can save data to the table.
        adapter.save({
            '_id': uuid.uuid4().hex,
            'domain': 'test',
            'doc_type': 'CommCareCase',
            'long_column': 'duplicate_choice_1(s)',
        })
        # and query it back
        q = adapter.get_query_object()
        self.assertEqual(1, q.count())


class ArrayTypeColumnDbTest(TestCase):

    def test_array_type_column(self):
        problem_spec = {
            "column_id": "referral_health_problem",
            "datatype": "array",
            "type": "expression",
            "expression": {
                "type": "split_string",
                "string_expression": {
                    "type": "property_name",
                    "property_name": "referral_health_problem",
                }
            },
        }
        data_source_config = DataSourceConfiguration(
            domain='test',
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=uuid.uuid4().hex,
            configured_filter={},
            configured_indicators=[problem_spec],
        )
        adapter = get_indicator_adapter(data_source_config)
        adapter.rebuild_table()
        self.addCleanup(adapter.drop_table)
        # ensure we can save data to the table.
        adapter.save({
            '_id': uuid.uuid4().hex,
            'domain': 'test',
            'doc_type': 'CommCareCase',
            'referral_health_problem': 'bleeding convulsions',
        })
        # and query it back
        qs = adapter.get_query_object()
        self.assertEqual(1, qs.count())
        self.assertEqual(qs.first().referral_health_problem, ['bleeding', 'convulsions'])


class TestExpandedColumn(TestCase):
    domain = 'foo'
    case_type = 'person'

    def _new_case(self, properties):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type=self.case_type,
            update=properties,
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})
        case = CommCareCase.get(id)
        self.addCleanup(case.delete)
        return case

    def _build_report(self, vals, field='my_field', build_data_source=True):
        """
        Build a new report, and populate it with cases.

        Return a ConfigurableReportDataSource and a FieldColumn
        :param vals: List of values to populate the given report field with.
        :param field: The name of a field in the data source/report
        :return: Tuple containing a ConfigurableReportDataSource and FieldColumn.
        The column is a column mapped to the given field.
        """

        # Create Cases
        for v in vals:
            update_props = {field: v} if v is not None else {}
            self._new_case(update_props).save()

        if build_data_source:
            tasks.rebuild_indicators(self.data_source_config._id)

        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source_config._id,
            title='foo',
            aggregation_columns=['doc_id'],
            columns=[{
                "type": "expanded",
                "field": field,
                "display": field,
                "format": "default",
            }],
            filters=[],
            configured_charts=[]
        )
        report_config.save()
        self.addCleanup(report_config.delete)
        data_source = ConfigurableReportDataSource.from_spec(report_config)

        return data_source, data_source.top_level_columns[0]

    @classmethod
    def setUpClass(cls):
        super(TestExpandedColumn, cls).setUpClass()
        cls.data_source_config = DataSourceConfiguration(
            domain=cls.domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=clean_table_name(cls.domain, str(uuid.uuid4().hex)),
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": cls.case_type,
            },
            configured_indicators=[{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": field
                },
                "column_id": field,
                "display_name": field,
                "datatype": "string"
            } for field in ['my_field', 'field_name_with_CAPITAL_letters']],
        )
        cls.data_source_config.save()

    @classmethod
    def tearDownClass(cls):
        cls.data_source_config.delete()
        super(TestExpandedColumn, cls).tearDownClass()

    def tearDown(self):
        adapter = get_indicator_adapter(self.data_source_config)
        adapter.drop_table()
        connection_manager.dispose_engine(UCR_ENGINE_ID)
        super(TestExpandedColumn, self).tearDown()

    def test_getting_distinct_values(self):
        data_source, column = self._build_report([
            'apple',
            'apple',
            'banana',
            'blueberry'
        ])
        vals = get_distinct_values(data_source.config, column)[0]
        self.assertListEqual(vals, ['apple', 'banana', 'blueberry'])

    def test_no_distinct_values(self):
        data_source, column = self._build_report([])
        distinct_vals, too_many_values = get_distinct_values(data_source.config, column)
        self.assertListEqual(distinct_vals, [])

    def test_too_large_expansion(self):
        vals = ['foo' + str(i) for i in range(DEFAULT_MAXIMUM_EXPANSION + 1)]
        data_source, column = self._build_report(vals)
        distinct_vals, too_many_values = get_distinct_values(data_source.config, column)
        self.assertTrue(too_many_values)
        self.assertEqual(len(distinct_vals), DEFAULT_MAXIMUM_EXPANSION)

    def test_allowed_expansion(self):
        num_columns = DEFAULT_MAXIMUM_EXPANSION + 1
        vals = ['foo' + str(i) for i in range(num_columns)]
        data_source, column = self._build_report(vals)
        column.max_expansion = num_columns
        distinct_vals, too_many_values = get_distinct_values(
            data_source.config,
            column,
            expansion_limit=num_columns,
        )
        self.assertFalse(too_many_values)
        self.assertEqual(len(distinct_vals), num_columns)

    def test_unbuilt_data_source(self):
        data_source, column = self._build_report(['apple'], build_data_source=False)
        distinct_vals, too_many_values = get_distinct_values(data_source.config, column)
        self.assertListEqual(distinct_vals, [])
        self.assertFalse(too_many_values)

    def test_expansion(self):
        column = ReportColumnFactory.from_spec(dict(
            type="expanded",
            field="lab_result",
            display="Lab Result",
            format="default",
            description="foo"
        ), is_static=False)
        cols = expand_column(column, ["positive", "negative"], "en")

        self.assertEqual(len(cols), 2)
        self.assertEqual(type(cols[0].view), SumWhen)
        self.assertEqual(cols[1].view.whens, {'negative': 1})

    def test_none_in_values(self):
        """
        Confirm that expanded columns work when one of the distinct values is None.
        This is an edge case because postgres uses different operators for comparing
        columns to null than it does for comparing to non-null values. e.g.
            "my_column = 4" vs "my_column is NULL"
        """
        field_name = 'field_name_with_CAPITAL_letters'
        submitted_vals = [None, None, 'foo']
        data_source, _ = self._build_report(submitted_vals, field=field_name)

        headers = [column.header for column in data_source.columns]
        self.assertEqual(set(headers), {"{}-{}".format(field_name, x) for x in submitted_vals})

        def get_expected_row(submitted_value, distinct_values):
            # The headers looks like "my_field-foo", but the rows are dicts with
            # keys like "my_field-1". So, we need use the index of the headers to
            # to determine which keys in the rows correspond to which values.
            row = {}
            for value in distinct_values:
                header_index = headers.index("{}-{}".format(field_name, value))
                row_key = "{}-{}".format(field_name, header_index)
                row[row_key] = 1 if submitted_value == value else 0
            return row

        expected_rows = [get_expected_row(v, set(submitted_vals)) for v in submitted_vals]
        data = data_source.get_data()
        self.assertItemsEqual(expected_rows, data)


class TestAggregateDateColumn(SimpleTestCase):

    def setUp(self):
        self._spec = {
            'type': 'aggregate_date',
            'column_id': 'a_date',
            'field': 'a_date',
        }

    def test_wrap(self):
        wrapped = ReportColumnFactory.from_spec(self._spec, is_static=False)
        self.assertTrue(isinstance(wrapped, AggregateDateColumn))
        self.assertEqual('a_date', wrapped.column_id)

    def test_group_by(self):
        wrapped = ReportColumnFactory.from_spec(self._spec, is_static=False)
        self.assertEqual(['a_date_year', 'a_date_month'], wrapped.get_query_column_ids())

    def test_format(self):
        wrapped = ReportColumnFactory.from_spec(self._spec, is_static=False)
        self.assertEqual('2015-03', wrapped.get_format_fn()({'year': 2015, 'month': 3}))

    def test_custom_format(self):
        self._spec.update({'format': '%b %Y'})
        wrapped = ReportColumnFactory.from_spec(self._spec, is_static=False)
        self.assertEqual('Mar 2015', wrapped.get_format_fn()({'year': 2015, 'month': 3}))

    def test_format_missing(self):
        wrapped = ReportColumnFactory.from_spec(self._spec, is_static=False)
        self.assertEqual('Unknown Date', wrapped.get_format_fn()({'year': None, 'month': None}))


class TestPercentageColumn(SimpleTestCase):

    def test_wrap(self):
        wrapped = ReportColumnFactory.from_spec({
            'type': 'percent',
            'column_id': 'pct',
            'numerator': {
                "aggregation": "sum",
                "field": "has_danger_signs",
                "type": "field",
            },
            'denominator': {
                "aggregation": "sum",
                "field": "is_pregnant",
                "type": "field",
            },
        }, is_static=False)
        self.assertTrue(isinstance(wrapped, PercentageColumn))
        self.assertEqual('pct', wrapped.column_id)
        self.assertEqual('has_danger_signs', wrapped.numerator.field)
        self.assertEqual('is_pregnant', wrapped.denominator.field)
        self.assertEqual('percent', wrapped.format)

    def test_missing_fields(self):
        field_spec = {
            "aggregation": "simple",
            "field": "is_pregnant",
            "type": "field",
        }
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
            }, is_static=False)
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
                'numerator': field_spec,
            }, is_static=False)
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
                'denominator': field_spec,
            }, is_static=False)

    def test_wrong_field_type(self):
        # can't put a percent in another percent
        field_spec = {
            "aggregation": "simple",
            "field": "is_pregnant",
            "type": "percent",
        }
        with self.assertRaises(BadSpecError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
                'numerator': field_spec,
                'denominator': field_spec,
            }, is_static=False)

    def test_format_pct(self):
        spec = self._test_spec()
        spec['format'] = 'percent'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        self.assertEqual('33%', wrapped.get_format_fn()({'num': 1, 'denom': 3}))

    def test_format_pct_denom_0(self):
        spec = self._test_spec()
        spec['format'] = 'percent'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        for empty_value in [0, 0.0, None, '']:
            self.assertEqual('--', wrapped.get_format_fn()({'num': 1, 'denom': empty_value}))

    def test_format_fraction(self):
        spec = self._test_spec()
        spec['format'] = 'fraction'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        self.assertEqual('1/3', wrapped.get_format_fn()({'num': 1, 'denom': 3}))

    def test_format_both(self):
        spec = self._test_spec()
        spec['format'] = 'both'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        self.assertEqual('33% (1/3)', wrapped.get_format_fn()({'num': 1, 'denom': 3}))

    def test_format_pct_non_numeric(self):
        spec = self._test_spec()
        spec['format'] = 'percent'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        for unexpected_value in ['hello', object()]:
            self.assertEqual('?', wrapped.get_format_fn()({'num': 1, 'denom': unexpected_value}),
                             'non-numeric value failed for denominator {}'. format(unexpected_value))
            self.assertEqual('?', wrapped.get_format_fn()({'num': unexpected_value, 'denom': 1}))

    def test_format_numeric_pct(self):
        spec = self._test_spec()
        spec['format'] = 'numeric_percent'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        self.assertEqual(33, wrapped.get_format_fn()({'num': 1, 'denom': 3}))

    def test_format_float(self):
        spec = self._test_spec()
        spec['format'] = 'decimal'
        wrapped = ReportColumnFactory.from_spec(spec, is_static=False)
        self.assertEqual(.333, wrapped.get_format_fn()({'num': 1, 'denom': 3}))
        self.assertEqual(.25, wrapped.get_format_fn()({'num': 1, 'denom': 4}))

    def _test_spec(self):
        return {
            'type': 'percent',
            'column_id': 'pct',
            'denominator': {
                "aggregation": "simple",
                "field": "is_pregnant",
                "type": "field",
            },
            'numerator': {
                "aggregation": "simple",
                "field": "has_danger_signs",
                "type": "field",
            }
        }
