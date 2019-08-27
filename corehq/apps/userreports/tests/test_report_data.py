from collections import namedtuple
from django.test import TestCase
import uuid

from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.tests.utils import doc_to_change
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.case import get_case_pillow
from six.moves import range


ReportDataTestRow = namedtuple('ReportDataTestRow', ['name', 'number', 'sort_key'])


class ReportDataTest(TestCase):

    def setUp(self):
        super(ReportDataTest, self).setUp()
        # Create report
        self.domain = 'test-ucr-report-data'
        self.data_source = DataSourceConfiguration(
            domain=self.domain,
            referenced_doc_type='CommCareCase',
            table_id=uuid.uuid4().hex,
            configured_filter={},
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'name'
                    },
                    "column_id": 'name',
                    "display_name": 'name',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'number'
                    },
                    "column_id": 'number',
                    "display_name": 'number',
                    "datatype": "integer"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'number'
                    },
                    "column_id": 'string-number',
                    "display_name": 'string-number',
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": 'just_for_sorting'
                    },
                    "column_id": 'just_for_sorting',
                    "display_name": 'just_for_sorting',
                    "datatype": "string"
                }
            ],
        )
        self.data_source.validate()
        self.data_source.save()
        self.adapter = get_indicator_adapter(self.data_source)
        self.adapter.rebuild_table()
        self.addCleanup(self.data_source.delete)

        # initialize a report on the data
        self.report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source._id,
            aggregation_columns=['doc_id'],
            columns=[
                {
                    "type": "field",
                    "field": "name",
                    "column_id": "name",
                    "display": "Name",
                    "aggregation": "simple",
                },
                {
                    "type": "field",
                    "field": "number",
                    "column_id": "number",
                    "display": "Number",
                    "aggregation": "simple",
                    "calculate_total": True,
                },
                {
                    "type": "expression",
                    "column_id": "ten",
                    "display": "The Number Ten",
                    "expression": {
                        'type': 'constant',
                        'constant': 10,
                    }
                },
                {
                    "type": "expression",
                    "column_id": "by_tens",
                    "display": "Counting by tens",
                    "expression": {
                        "type": "evaluator",
                        "statement": "a * b",
                        "context_variables": {
                            "a": {
                                "type": "property_name",
                                "property_name": "number",
                            },
                            "b": {
                                "type": "property_name",
                                "property_name": "ten",
                            }
                        }
                    }
                },
                {
                    "type": "field",
                    "field": 'string-number',
                    "display": 'Display Number',
                    "aggregation": "simple",
                    "transform": {
                        "type": "translation",
                        "translations": {
                            "0": "zero",
                            "1": {"en": "one", "es": "uno"},
                            "2": {"en": "two", "es": "dos"}
                        },
                    },
                }
            ],
            filters=[],
            configured_charts=[],
            sort_expression=[{'field': 'just_for_sorting', 'order': 'DESC'}]
        )
        self.report_config.save()
        self.addCleanup(self.report_config.delete)

    def _add_some_rows(self, count):
        rows = [ReportDataTestRow(uuid.uuid4().hex, i, i) for i in range(count)]
        self._add_rows(rows)
        return rows

    def _add_rows(self, rows):
        pillow = get_case_pillow(ucr_configs=[self.data_source])

        def _get_case(row):
            return {
                '_id': uuid.uuid4().hex,
                'domain': self.domain,
                'doc_type': 'CommCareCase',
                'type': 'city',
                'name': row.name,
                'number': row.number,
                'just_for_sorting': row.sort_key,
            }
        for row in rows:
            pillow.process_change(doc_to_change(_get_case(row)))

    def test_basic_query(self):
        # add a few rows to the data source
        rows = self._add_some_rows(3)

        # check the returned data from the report looks right
        report_data_source = ConfigurableReportDataSource.from_spec(self.report_config)
        report_data = report_data_source.get_data()
        self.assertEqual(len(rows), len(report_data))
        rows_by_name = {r.name: r for r in rows}
        for row in report_data:
            self.assertTrue(row['name'] in rows_by_name)
            self.assertEqual(rows_by_name[row['name']].number, row['number'])
            self.assertEqual(10, row['ten'])
            self.assertEqual(10 * row['number'], row['by_tens'])

    def test_limit(self):
        count = 5
        self._add_some_rows(count)
        report_data_source = ConfigurableReportDataSource.from_spec(self.report_config)
        original_data = report_data_source.get_data()
        self.assertEqual(count, len(original_data))
        limited_data = report_data_source.get_data(limit=3)
        self.assertEqual(3, len(limited_data))
        self.assertEqual(original_data[:3], limited_data)

    def test_skip(self):
        count = 5
        self._add_some_rows(count)
        report_data_source = ConfigurableReportDataSource.from_spec(self.report_config)
        original_data = report_data_source.get_data()
        self.assertEqual(count, len(original_data))
        skipped = report_data_source.get_data(start=3)
        self.assertEqual(count - 3, len(skipped))
        self.assertEqual(original_data[3:], skipped)

    def test_total_row(self):
        rows = self._add_some_rows(3)
        report_data_source = ConfigurableReportDataSource.from_spec(self.report_config)

        total_number = sum(row.number for row in rows)
        self.assertEqual(report_data_source.get_total_row(), ['Total', total_number, '', '', ''])

    def test_transform(self):
        count = 5
        self._add_some_rows(count)
        report_data_source = ConfigurableReportDataSource.from_spec(self.report_config)
        original_data = report_data_source.get_data()
        self.assertEqual(count, len(original_data))
        rows_by_number = {int(row['number']): row for row in original_data}
        # Make sure the translations happened
        self.assertEqual(rows_by_number[0]['string-number'], "zero")
        self.assertEqual(rows_by_number[1]['string-number'], "one")
        self.assertEqual(rows_by_number[2]['string-number'], "two")
        # These last two are untranslated
        self.assertEqual(rows_by_number[3]['string-number'], "3")
        self.assertEqual(rows_by_number[4]['string-number'], "4")
