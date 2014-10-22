import json
import os
from datetime import date
from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.models import DataSourceConfiguration


class DataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_indicator_config.json')
        with open(sample_file) as f:
            structure = json.loads(f.read())
            self.config = DataSourceConfiguration.wrap(structure)

    def testMetadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommCareCase', self.config.referenced_doc_type)
        self.assertEqual('CommBugz', self.config.display_name)
        self.assertEqual('sample', self.config.table_id)

    def testFilters(self):
        # filters
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertFalse(self.config.filter.filter(document))
            self.assertEqual([], self.config.get_values(document))

        self.assertTrue(self.config.filter.filter(
            dict(doc_type="CommCareCase", domain='user-reports', type='ticket')
        ))

    def testColumns(self):
        # columns
        expected_columns = [
            'doc_id',
            'date',
            'owner',
            'count',
            'category_bug', 'category_feature', 'category_app', 'category_schedule',
            'tags_easy-win', 'tags_potential-dupe', 'tags_roadmap', 'tags_public',
            'is_starred',
            'estimate'
        ]
        cols = self.config.get_columns()
        self.assertEqual(len(expected_columns), len(cols))
        for i, col in enumerate(expected_columns):
            col_back = cols[i]
            self.assertEqual(col, col_back.id)

    def testIndicators(self):
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators()
        results = self.config.get_values(sample_doc)
        for result in results:
            self.assertEqual(expected_indicators[result.column.id], result.value)


def get_sample_doc_and_indicators():
    date_opened = date(2014, 6, 21)
    sample_doc = dict(
        _id='some-doc-id',
        opened_on=date_opened,
        owner_id='some-user-id',
        doc_type="CommCareCase",
        domain='user-reports',
        type='ticket',
        category='bug',
        tags='easy-win public',
        is_starred='yes',
        estimate=2,
    )
    expected_indicators = {
        'doc_id': 'some-doc-id',
        'date': date_opened,
        'owner': 'some-user-id',
        'count': 1,
        'category_bug': 1, 'category_feature': 0, 'category_app': 0, 'category_schedule': 0,
        'tags_easy-win': 1, 'tags_potential-dupe': 0, 'tags_roadmap': 0, 'tags_public': 1,
        'is_starred': 1,
        'estimate': 2,
    }
    return sample_doc, expected_indicators


class DataSourceConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        DataSourceConfiguration(domain='foo', table_id='foo1', referenced_doc_type='doc1').save()
        DataSourceConfiguration(domain='foo', table_id='foo2', referenced_doc_type='doc2').save()
        DataSourceConfiguration(domain='bar', table_id='bar1', referenced_doc_type='doc3').save()

    @classmethod
    def tearDownClass(cls):
        for config in DataSourceConfiguration.all():
            config.delete()

    def testGetByDomain(self):
        results = DataSourceConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.table_id in ('foo1', 'foo2'))

        results = DataSourceConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def testGetAll(self):
        self.assertEqual(3, len(list(DataSourceConfiguration.all())))

    def testDomainIsRequired(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(table_id='table',
                                    referenced_doc_type='doc').save()

    def testTableIdIsRequired(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain',
                                    referenced_doc_type='doc').save()

    def testDocTypeIsRequired(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain', table_id='table').save()


class IndicatorNamedFilterTest(SimpleTestCase):
    def setUp(self):
        self.indicator_configuration = DataSourceConfiguration.wrap({
            'display_name': 'Mother Indicators',
            'doc_type': 'DataSourceConfiguration',
            'domain': 'test',
            'referenced_doc_type': 'CommCareCase',
            'table_id': 'mother_indicators',
            'named_filters': {
                'pregnant': {
                    'type': 'property_match',
                    'property_name': 'mother_state',
                    'property_value': 'pregnant',
                }
            },
            'configured_filter': {
                'type': 'and',
                'filters': [
                    {
                        'property_name': 'type',
                        'property_value': 'ttc_mother',
                        'type': 'property_match',
                    },
                    {
                        'type': 'named',
                        'name': 'pregnant',
                    }
                ]
            }
        })

    def test_match(self):
        self.assertTrue(self.indicator_configuration.filter.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant'
        }))

    def test_no_match(self):
        self.assertFalse(self.indicator_configuration.filter.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'not pregnant'
        }))
