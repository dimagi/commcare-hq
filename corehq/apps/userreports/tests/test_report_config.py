import json
import os
from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.models import ReportConfiguration, DataSourceConfiguration


class ReportConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = _get_sample_config()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommBugz', self.config.title)
        self.assertEqual('12345', self.config.config_id)

    def test_sample_config_is_valid(self):
        self.config.validate()


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

    def testGetByDomain(self):
        results = ReportConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.config_id in ('foo1', 'foo2'))

        results = ReportConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def testGetAll(self):
        self.assertEqual(3, len(list(ReportConfiguration.all())))

    def testDomainIsRequired(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(config_id='foo').save()

    def testConfigIdIsRequired(self):
        with self.assertRaises(BadValueError):
            ReportConfiguration(domain='foo').save()

    def testSampleConfigIsValid(self):
        config = _get_sample_config()
        config.validate()


def _get_sample_config():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_report_config.json')
    with open(sample_file) as f:
        structure = json.loads(f.read())
        return ReportConfiguration.wrap(structure)
