from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from jsonobject.exceptions import BadValueError

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.dbaccessors import get_all_report_configs
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_report_config,
    mock_datasource_config,
)


@patch('corehq.apps.userreports.models.AllowedUCRExpressionSettings.disallowed_ucr_expressions', MagicMock(return_value=[]))
class ReportConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_report_config()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommBugz', self.config.title)
        self.assertEqual('12345', self.config.config_id)

    def test_duplicate_filter_slugs(self):
        spec = self.config._doc
        spec['filters'].append(spec['filters'][-1])
        wrapped = ReportConfiguration.wrap(spec)
        with self.assertRaises(BadSpecError):
            wrapped.validate()

    def test_duplicate_column_ids(self):
        spec = self.config._doc
        spec['columns'].append(spec['columns'][-1])
        wrapped = ReportConfiguration.wrap(spec)
        with self.assertRaises(BadSpecError):
            wrapped.validate()

    def test_duplicate_column_ids_pct_columns(self):
        spec = self.config._doc
        spec['columns'].append({
            'type': 'percent',
            'column_id': 'pct',
            'numerator': {
                "aggregation": "sum",
                "field": "pct_numerator",
                "type": "field",
                "column_id": "pct_numerator",
            },
            'denominator': {
                "aggregation": "sum",
                "field": spec['columns'][-1]["field"],
                "type": "field",
            },
        })
        wrapped = ReportConfiguration.wrap(spec)
        with self.assertRaises(BadSpecError):
            wrapped.validate()

    def test_group_by_missing_from_columns(self):
        report_config = ReportConfiguration(
            domain='somedomain',
            config_id='someconfig',
            aggregation_columns=['doc_id'],
            columns=[{
                "type": "field",
                "field": "somefield",
                "format": "default",
                "aggregation": "sum"
            }],
            filters=[],
            configured_charts=[]
        )
        data_source = ConfigurableReportDataSource.from_spec(report_config)
        with mock_datasource_config():
            self.assertEqual(['doc_id'], data_source.group_by)

    def test_fall_back_display_to_column_id(self):
        config = ReportConfiguration(
            domain='somedomain',
            config_id='someconfig',
            aggregation_columns=['doc_id'],
            columns=[{
                "type": "field",
                "column_id": "my_column",
                "field": "somefield",
                "format": "default",
                "aggregation": "sum"
            }],
            filters=[],
            configured_charts=[]
        )
        self.assertEqual(config.report_columns[0].display, 'my_column')

    def test_missing_column_id(self):
        config = ReportConfiguration(
            domain='somedomain',
            config_id='someconfig',
            aggregation_columns=['doc_id'],
            columns=[{
                'type': 'percent',
                #  'column_id': 'pct',
                'numerator': {
                    "aggregation": "sum",
                    "field": "pct_numerator",
                    "type": "field",
                    "column_id": "pct_numerator",
                },
                'denominator': {
                    "aggregation": "sum",
                    "field": "pct_denominator",
                    "type": "field",
                },
            }],
            filters=[],
            configured_charts=[]
        )
        with self.assertRaises(BadSpecError):
            config.validate()

    def test_constant_date_expression_column(self):
        """
        Used to fail at jsonobject.base_properties.AbstractDateProperty.wrap:

            BadValueError: datetime.date(2020, 9, 9) is not a date-formatted string
        """
        spec = self.config._doc
        spec['columns'].append({
          "type": "expression",
          "column_id": "month",
          "display": "month",
          "transform": {
            "type": "custom",
            "custom_type": "month_display"
          },
          "expression": {
            "type": "constant",
            "constant": "2020-09-09"
          }
        })
        wrapped = ReportConfiguration.wrap(spec)
        wrapped.validate()


class ReportConfigurationDBAccessorsTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_foo = Domain(name='foo')
        cls.domain_foo.save()
        cls.addClassCleanup(cls.domain_foo.delete)

        cls.domain_bar = Domain(name='bar')
        cls.domain_bar.save()
        cls.addClassCleanup(cls.domain_bar.delete)

        for name, config_id in [(cls.domain_foo.name, 'foo1'),
                                (cls.domain_foo.name, 'foo2'),
                                (cls.domain_bar.name, 'bar1')]:
            config = ReportConfiguration(domain=name, config_id=config_id)
            config.save()
            cls.addClassCleanup(config.delete)

    def test_by_domain_returns_relevant_report_configs(self):
        results = ReportConfiguration.by_domain('foo')
        self.assertEqual(len(results), 2)
        self.assertEqual({r.config_id for r in results}, {'foo1', 'foo2'})

    def test_by_domain_returns_empty(self):
        results = ReportConfiguration.by_domain('not-foo')
        self.assertEqual(results, [])

    def test_get_all_report_configs_returns_expected_result(self):
        results = list(get_all_report_configs())
        self.assertEqual(len(results), 3)
        self.assertEqual({r.config_id for r in results},
                         {'foo1', 'foo2', 'bar1'})

    def test_create_requires_domain(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(config_id='foo').save()

    def test_create_requires_config_id(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(domain='foo').save()


class ReportTranslationTest(TestCase):

    DOMAIN = 'foo-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data_source = DataSourceConfiguration(
            domain=cls.DOMAIN,
            table_id="foo",
            referenced_doc_type="CommCareCase",
        )
        data_source.save()
        cls.addClassCleanup(data_source.delete)

        cls.report = ReportConfiguration(
            domain=cls.DOMAIN,
            config_id=data_source._id,
            columns=[
                {
                    "type": "field",
                    "field": "foo",
                    "column_id": "foo",
                    "aggregation": "simple",
                    "display": "My Column",
                },
                {
                    "type": "field",
                    "field": "bar",
                    "column_id": "bar",
                    "aggregation": "simple",
                    "display": {"en": "Name", "fra": "Nom"},
                },
            ]
        )
        cls.report.save()
        cls.addClassCleanup(cls.report.delete)
        cls.report_source = ConfigurableReportDataSource.from_spec(cls.report)

    def test_column_string_display_value(self):
        self.assertEqual(self.report_source.columns[0].header, "My Column")
        self.report_source.lang = "fra"
        self.assertEqual(self.report_source.columns[0].header, "My Column")

    def test_column_display_translation(self):
        # Default to english translation if no language given.
        self.assertEqual(self.report_source.columns[1].header, "Name")

        self.report_source.lang = "en"
        self.assertEqual(self.report_source.columns[1].header, "Name")

        self.report_source.lang = "fra"
        self.assertEqual(self.report_source.columns[1].header, "Nom")

        # Default to english if missing language given
        self.report_source.lang = "hin"
        self.assertEqual(self.report_source.columns[1].header, "Name")
