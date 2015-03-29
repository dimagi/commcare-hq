import uuid

from jsonobject.exceptions import BadValueError
from sqlagg import SumWhen
from django.test import SimpleTestCase, TestCase

from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.factory import ReportFactory, ReportColumnFactory
from corehq.apps.userreports.reports.specs import FieldColumn, PercentageColumn
from corehq.apps.userreports.sql import _expand_column, _get_distinct_values

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2


class TestFieldColumn(SimpleTestCase):

    def testColumnSetFromAlias(self):
        field = ReportColumnFactory.from_spec({
            "aggregation": "simple",
            "field": "doc_id",
            "alias": "the_right_answer",
            "type": "field",
        })
        self.assertTrue(isinstance(field, FieldColumn))
        self.assertEqual('the_right_answer', field.column_id)

    def testColumnDefaultsToField(self):
        field = ReportColumnFactory.from_spec({
            "aggregation": "simple",
            "field": "doc_id",
            "type": "field",
        })
        self.assertEqual('doc_id', field.column_id)

    def testBadAggregation(self):
        with self.assertRaises(BadValueError):
            ReportColumnFactory.from_spec({
                "aggregation": "simple_",
                "field": "doc_id",
                "type": "field",
            })

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
                })
            ))

    def testBadFormat(self):
        with self.assertRaises(BadValueError):
            ReportColumnFactory.from_spec({
                "aggregation": "simple",
                "field": "doc_id",
                "format": "default_",
                "type": "field",
            })


class TestExpandFieldColumn(TestCase):
    domain = 'foo'
    case_type = 'person'

    def _new_case(self, properties):
        id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=id,
            case_type=self.case_type,
            version=V2,
            update=properties,
        ).as_xml()
        post_case_blocks([case_block], {'domain': self.domain})
        return CommCareCase.get(id)

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
            self._new_case({field: v}).save()

        # Create report
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": self.case_type,
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
            }],
        )
        data_source_config.validate()
        data_source_config.save()
        if build_data_source:
            tasks.rebuild_indicators(data_source_config._id)

        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title='foo',
            aggregation_columns=['doc_id'],
            columns=[{
                "type": "field",
                "field": field,
                "display": field,
                "format": "default",
                "aggregation": "expand",
            }],
            filters=[],
            configured_charts=[]
        )
        report_config.save()
        data_source = ReportFactory.from_spec(report_config)

        return data_source, data_source.column_configs[0]

    def setUp(self):
        delete_all_cases()

    def test_getting_distinct_values(self):
        data_source, column = self._build_report([
            'apple',
            'apple',
            'banana',
            'blueberry'
        ])
        vals = _get_distinct_values(data_source.config, column)[0]
        self.assertSetEqual(set(vals), set(['apple', 'banana', 'blueberry']))

    def test_no_distinct_values(self):
        data_source, column = self._build_report([])
        distinct_vals, too_many_values = _get_distinct_values(data_source.config, column)
        self.assertListEqual(distinct_vals, [])

    def test_too_large_expansion(self):
        vals = ['foo' + str(i) for i in range(11)]
        # Maximum expansion width is 10
        data_source, column = self._build_report(vals)
        distinct_vals, too_many_values = _get_distinct_values(data_source.config, column)
        self.assertTrue(too_many_values)
        self.assertEqual(len(distinct_vals), 10)

    def test_unbuilt_data_source(self):
        data_source, column = self._build_report(['apple'], build_data_source=False)
        distinct_vals, too_many_values = _get_distinct_values(data_source.config, column)
        self.assertListEqual(distinct_vals, [])
        self.assertFalse(too_many_values)

    def test_expansion(self):
        column = ReportColumnFactory.from_spec(dict(
            type="field",
            field="lab_result",
            display="Lab Result",
            format="default",
            aggregation="expand",
            description="foo"
        ))
        cols = _expand_column(column, ["positive", "negative"])

        self.assertEqual(len(cols), 2)
        self.assertEqual(type(cols[0].view), SumWhen)
        self.assertEqual(cols[1].view.whens, {'negative': 1})


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
        })
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
        with self.assertRaises(BadValueError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
            })
        with self.assertRaises(BadValueError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
                'numerator': field_spec,
            })
        with self.assertRaises(BadValueError):
            ReportColumnFactory.from_spec({
                'type': 'percent',
                'column_id': 'pct',
                'denominator': field_spec,
            })
