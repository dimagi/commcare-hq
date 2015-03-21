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
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.specs import ReportColumn
from corehq.apps.userreports.sql import _expand_column, _get_distinct_values

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2


class TestReportColumn(SimpleTestCase):
    def testBadAggregation(self):
        with self.assertRaises(BadValueError):
            ReportColumn.wrap({
                "aggregation": "simple_",
                "field": "doc_id",
                "type": "field",
            })

    def testGoodFormat(self):
        for format in [
            'default',
            'percent_of_total',
        ]:
            self.assertEquals(ReportColumn, type(
                ReportColumn.wrap({
                    "aggregation": "simple",
                    "field": "doc_id",
                    "format": format,
                    "type": "field",
                })
            ))

    def testBadFormat(self):
        with self.assertRaises(BadValueError):
            ReportColumn.wrap({
                "aggregation": "simple",
                "field": "doc_id",
                "format": "default_",
                "type": "field",
            })


class TestExpandReportColumn(TestCase):
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

    def test_getting_distinct_values(self):

        # Create Cases
        for x in ['apple', 'apple', 'banana', 'blueberry']:
            self._new_case({'fruit': x}).save()

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
                    "property_name": "fruit"
                },
                "column_id": "fruit",
                "display_name": "fruit",
                "datatype": "string"
            }],
        )
        data_source_config.validate()
        data_source_config.save()
        tasks.rebuild_indicators(data_source_config._id)

        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title='foo',
            aggregation_columns=['doc_id'],
            columns=[{
                "type": "field",
                "field": "fruit",
                "display": "Fruit",
                "format": "default",
                "aggregation": "expand",
            }],
            filters=[],
            configured_charts=[]
        )
        report_config.save()
        data_source = ReportFactory.from_spec(report_config)

        # Get distinct values
        vals = _get_distinct_values(data_source.config, data_source.column_configs[0])[0]
        self.assertSetEqual(set(vals), set(['apple', 'banana', 'blueberry']))

    def test_expansion(self):
        column = ReportColumn(
            type="field",
            field="lab_result",
            display="Lab Result",
            format="default",
            aggregation="expand",
            description="foo"
        )
        cols = _expand_column(column, ["positive", "negative"])

        self.assertEqual(len(cols), 2)
        self.assertEqual(type(cols[0].view), SumWhen)
        self.assertEqual(cols[1].view.whens, {'negative':1})
