import json
import os
from datetime import date
from django.test import SimpleTestCase, TestCase
from corehq.apps.userreports.models import IndicatorConfiguration


class IndicatorConfigurationTest(SimpleTestCase):


    def setUp(self):
        folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
        sample_file = os.path.join(folder, 'sample_config.json')
        with open(sample_file) as f:
            structure = json.loads(f.read())
            self.config = IndicatorConfiguration.wrap(structure)

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

        self.assertTrue(self.config.filter.filter(dict(doc_type="CommCareCase", domain='user-reports', type='ticket')))

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


class IndicatorConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        IndicatorConfiguration(domain='foo', table_id='foo1').save()
        IndicatorConfiguration(domain='foo', table_id='foo2').save()
        IndicatorConfiguration(domain='bar', table_id='bar1').save()

    @classmethod
    def tearDownClass(cls):
        for config in IndicatorConfiguration.all():
            config.delete()

    def testGetByDomain(self):
        results = IndicatorConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.table_id in ('foo1', 'foo2'))

        results = IndicatorConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def testGetAll(self):
        self.assertEqual(3, len(list(IndicatorConfiguration.all())))
