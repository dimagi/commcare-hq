import json
import os
from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import ReportConfiguration, IndicatorConfiguration


class ReportConfigurationTest(SimpleTestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_report_config.json')
        with open(sample_file) as f:
            structure = json.loads(f.read())
            self.config = ReportConfiguration.wrap(structure)

    def testMetadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommBugz', self.config.display_name)
        self.assertEqual('12345', self.config.config_id)


class ReportConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        shared_kwargs = {
            'referenced_doc_type': 'doc',
            'table_id': 'table',
        }
        IndicatorConfiguration(domain='foo', _id='foo1', **shared_kwargs).save()
        IndicatorConfiguration(domain='foo', _id='foo2', **shared_kwargs).save()
        IndicatorConfiguration(domain='bar', _id='bar1', **shared_kwargs).save()
        ReportConfiguration(domain='foo', config_id='foo1').save()
        ReportConfiguration(domain='foo', config_id='foo2').save()
        ReportConfiguration(domain='bar', config_id='bar1').save()

    @classmethod
    def tearDownClass(cls):
        for config in IndicatorConfiguration.all():
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

    def testConfigMustExist(self):
        with self.assertRaises(BadSpecError):
            ReportConfiguration(domain='foo', config_id='notreal').save()
