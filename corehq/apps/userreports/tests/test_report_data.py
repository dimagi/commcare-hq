from collections import namedtuple
import uuid
from django.test import TestCase
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.apps.userreports.pillow import get_kafka_ucr_pillow
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.tests.utils import doc_to_change


ReportDataTestRow = namedtuple('ReportDataTestRow', ['name', 'number'])


class ReportDataTest(TestCase):
    dependent_apps = ['pillowtop']

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
                }
            ],
        )
        self.data_source.validate()
        self.data_source.save()
        IndicatorSqlAdapter(self.data_source).rebuild_table()
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
                }
            ],
            filters=[],
            configured_charts=[]
        )
        self.report_config.save()
        self.addCleanup(self.report_config.delete)

    def _add_some_rows(self, count):
        rows = [ReportDataTestRow(uuid.uuid4().hex, i) for i in range(count)]
        self._add_rows(rows)
        return rows

    def _add_rows(self, rows):
        pillow = get_kafka_ucr_pillow()
        pillow.bootstrap(configs=[self.data_source])

        def _get_case(row):
            return {
                '_id': uuid.uuid4().hex,
                'domain': self.domain,
                'doc_type': 'CommCareCase',
                'type': 'city',
                'name': row.name,
                'number': row.number,
            }
        for row in rows:
            pillow.process_change(doc_to_change(_get_case(row)))

    def test_basic_query(self):
        # add a few rows to the data source
        rows = self._add_some_rows(3)

        # check the returned data from the report looks right
        report_data_source = ReportFactory.from_spec(self.report_config)
        report_data = report_data_source.get_data()
        self.assertEqual(len(rows), len(report_data))
        rows_by_name = {r.name: r for r in rows}
        for row in report_data:
            self.assertTrue(row['name'] in rows_by_name)
            self.assertEqual(rows_by_name[row['name']].number, row['number'])

    def test_limit(self):
        count = 5
        self._add_some_rows(count)
        report_data_source = ReportFactory.from_spec(self.report_config)
        original_data = report_data_source.get_data()
        self.assertEqual(count, len(original_data))
        limited_data = report_data_source.get_data(limit=3)
        self.assertEqual(3, len(limited_data))
        self.assertEqual(original_data[:3], limited_data)

    def test_skip(self):
        count = 5
        self._add_some_rows(count)
        report_data_source = ReportFactory.from_spec(self.report_config)
        original_data = report_data_source.get_data()
        self.assertEqual(count, len(original_data))
        skipped = report_data_source.get_data(start=3)
        self.assertEqual(count - 3, len(skipped))
        self.assertEqual(original_data[3:], skipped)
