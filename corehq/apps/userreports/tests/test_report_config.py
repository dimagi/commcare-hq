from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import ReportConfiguration, DataSourceConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.tests.utils import get_sample_report_config


class ReportConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_report_config()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommBugz', self.config.title)
        self.assertEqual('12345', self.config.config_id)

    def test_sample_config_is_valid(self):
        self.config.validate()

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
        data_source = ReportFactory.from_spec(report_config)
        self.assertEqual(['doc_id'], data_source.group_by)


class ReportConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        ReportConfiguration(domain='foo', config_id='foo1').save()
        ReportConfiguration(domain='foo', config_id='foo2').save()
        ReportConfiguration(domain='bar', config_id='bar1').save()

    @classmethod
    def tearDownClass(cls):
        for config in DataSourceConfiguration.all():
            config.delete()
        for config in ReportConfiguration.all():
            config.delete()

    def test_get_by_domain(self):
        results = ReportConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.config_id in ('foo1', 'foo2'))

        results = ReportConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def test_get_all(self):
        self.assertEqual(3, len(list(ReportConfiguration.all())))

    def test_domain_is_required(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(config_id='foo').save()

    def test_config_id_is_required(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(domain='foo').save()

    def test_sample_config_is_valid(self):
        config = get_sample_report_config()
        config.validate()
