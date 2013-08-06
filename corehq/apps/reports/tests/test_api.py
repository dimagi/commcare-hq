from datetime import date
from django import test as unittest
from sqlagg.columns import SimpleColumn, SumColumn
from corehq.apps.reports.api import ReportApiSource, ConfigItemMeta, IndicatorMeta, get_report_results
from corehq.apps.reports.datatables import DataTablesColumnGroup
from corehq.apps.reports.sqlreport import SqlReportApiSource, SqlData, DatabaseColumn
from corehq.apps.reports.tests.sql_fixture import load_data

DOMAIN = "test"


class TestReport(ReportApiSource):
    slug = 'test'
    name = 'Test'

    @property
    def config_meta(self):
        return [ConfigItemMeta('date', 'Date', 'date', required=True)]

    @property
    def indicators_meta(self):
        return [IndicatorMeta('test', 'Test')]

    def results(self):
        return [dict(test=1)]


class TestSqlData(SqlData):
    name = 'Test SQL report API test'
    slug = 'sql_test'
    table_name = 'user_report_data'

    @property
    def filters(self):
        return ['date between :startdate and :enddate']

    @property
    def filter_values(self):
        return dict(startdate=self.datespan.startdate_param_utc,
                    enddate=self.datespan.enddate_param_utc)

    @property
    def group_by(self):
        return ['user']

    @property
    def columns(self):
        test_group = DataTablesColumnGroup("Category of abuse")
        return [
            DatabaseColumn("User", SimpleColumn("user")),
            DatabaseColumn("Indicator A", SumColumn("indicator_a")),
            DatabaseColumn("Indicator B", SumColumn("indicator_b")),
            DatabaseColumn("Indicator B", SumColumn("indicator_c"), header_group=test_group),
            DatabaseColumn("Indicator B", SumColumn("indicator_d"), header_group=test_group)
        ]


class TestSqlReport(SqlReportApiSource):
    sqldata_class = TestSqlData

    @property
    def config_meta(self):
        return [
            ConfigItemMeta('startdate', 'Start Date', 'date', default=date(2013, 1, 1)),
            ConfigItemMeta('enddate', 'End Date', 'date', default=date(2013, 2, 1)),
            ConfigItemMeta('user', 'User', 'string', group_by=True),
        ]


class ReportApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_data()

    def test_api_config_complete(self):
        result = get_report_results(TestReport, DOMAIN, dict(date='2013-01-01'))
        self.assertEqual(result, dict(results=[dict(test=1)]))

    def test_api_config_incomplete(self):
        with self.assertRaisesRegexp(ValueError, "Report config incomplete. Missing config params: \['date'\]"):
            get_report_results(TestReport, DOMAIN, dict())

    def test_sql_report_api(self):
        result = get_report_results(TestSqlReport, DOMAIN, dict())
        expected = {'results': [
            {'indicator_a': 1L, 'indicator_b': 1L,
             'indicator_c': 2L, 'indicator_d': 4L, 'user': 'user2'},
            {'indicator_a': 1L, 'indicator_b': 1L,
             'indicator_c': 2L, 'indicator_d': 2L, 'user': 'user1'}]}
        self.assertEqual(result, expected)

    def test_sql_report_api_select_indicators(self):
        result = get_report_results(TestSqlReport, DOMAIN, dict(), indicator_slugs=['indicator_a'])
        expected = {'results': [
            {'indicator_a': 1L, 'user': 'user2'},
            {'indicator_a': 1L, 'user': u'user1'}]}
        self.assertEqual(result, expected)
