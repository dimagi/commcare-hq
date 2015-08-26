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


class ReportTranslationTest(TestCase):

    DOMAIN = 'foo-domain'

    @classmethod
    def setUpClass(cls):
        data_source = DataSourceConfiguration(
            domain=cls.DOMAIN,
            table_id="foo",
            referenced_doc_type="CommCareCase",
        )
        data_source.save()
        ReportConfiguration(
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
        ).save()

    @classmethod
    def tearDownClass(cls):
        for config in DataSourceConfiguration.all():
            config.delete()
        for config in ReportConfiguration.all():
            config.delete()

    def setUp(self):
        report = ReportConfiguration.by_domain(self.DOMAIN)[0]
        self.report_source = ReportFactory.from_spec(report)

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
