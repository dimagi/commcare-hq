import json
import os
import datetime
from decimal import Decimal
from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.models import DataSourceConfiguration, \
    CustomDataSourceConfiguration


class DataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_data_source()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommCareCase', self.config.referenced_doc_type)
        self.assertEqual('CommBugz', self.config.display_name)
        self.assertEqual('sample', self.config.table_id)

    def test_filters(self):
        # filters
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertFalse(self.config.filter(document))
            self.assertEqual([], self.config.get_all_values(document))

        doc = dict(doc_type="CommCareCase", domain='user-reports', type='ticket')
        self.assertTrue(self.config.filter(doc))

    def test_columns(self):
        # columns
        expected_columns = [
            'doc_id',
            'date',
            'owner',
            'count',
            'category_bug', 'category_feature', 'category_app', 'category_schedule',
            'tags_easy-win', 'tags_potential-dupe', 'tags_roadmap', 'tags_public',
            'is_starred',
            'estimate',
            'priority'
        ]
        cols = self.config.get_columns()
        self.assertEqual(len(expected_columns), len(cols))
        for i, col in enumerate(expected_columns):
            col_back = cols[i]
            self.assertEqual(col, col_back.id)

    def test_indicators(self):
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators()
        [results] = self.config.get_all_values(sample_doc)
        for result in results:
            try:
                self.assertEqual(expected_indicators[result.column.id], result.value)
            except AssertionError:
                # todo: this is a hack due to the fact that type conversion currently happens
                # in the database layer. this should eventually be fixed.
                self.assertEqual(str(expected_indicators[result.column.id]), result.value)

    def test_serializable_custom_configs(self):
        for config in CustomDataSourceConfiguration.all():
            # There are some serialization issues with custom configurations.
            config.to_json()


def get_sample_data_source():
    folder = os.path.join(os.path.dirname(__file__), 'data', 'configs')
    sample_file = os.path.join(folder, 'sample_data_source.json')
    with open(sample_file) as f:
        structure = json.loads(f.read())
        return DataSourceConfiguration.wrap(structure)


def get_sample_doc_and_indicators():
    date_opened = "2014-06-21"
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
        estimate=2.3,
        priority=4,
    )
    expected_indicators = {
        'doc_id': 'some-doc-id',
        'date': datetime.datetime.strptime(date_opened, '%Y-%m-%d').date(),
        'owner': 'some-user-id',
        'count': 1,
        'category_bug': 1, 'category_feature': 0, 'category_app': 0, 'category_schedule': 0,
        'tags_easy-win': 1, 'tags_potential-dupe': 0, 'tags_roadmap': 0, 'tags_public': 1,
        'is_starred': 1,
        'estimate': Decimal(2.3),
        'priority': 4,
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

    def test_get_by_domain(self):
        results = DataSourceConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.table_id in ('foo1', 'foo2'))

        results = DataSourceConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def test_get_all(self):
        self.assertEqual(3, len(list(DataSourceConfiguration.all())))

    def test_domain_is_required(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(table_id='table',
                                    referenced_doc_type='doc').save()

    def test_table_id_is_required(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain',
                                    referenced_doc_type='doc').save()

    def test_doc_type_is_required(self):
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
                },
                'evil': {
                    'type': 'property_match',
                    'property_name': 'evil',
                    'property_value': 'yes',
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
            },
            'configured_indicators': [
                {
                    "type": "boolean",
                    "column_id": "is_evil",
                    "filter": {
                        "type": "named",
                        "name": "evil"
                    }
                },
                {
                    "type": "expression",
                    "column_id": "laugh_sound",
                    "datatype": "string",
                    "expression": {
                        'type': 'conditional',
                        'test': {
                            "type": "named",
                            "name": "evil"
                        },
                        'expression_if_true': {
                            'type': 'constant',
                            'constant': 'mwa-ha-ha',
                        },
                        'expression_if_false': {
                            'type': 'constant',
                            'constant': 'hehe',
                        },
                    }
                }
            ]
        })

    def test_match(self):
        self.assertTrue(self.indicator_configuration.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant'
        }))

    def test_no_match(self):
        self.assertFalse(self.indicator_configuration.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'not pregnant'
        }))

    def test_simple_indicator_match(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'yes'
        })
        self.assertEqual(1, values[1].value)

    def test_simple_indicator_nomatch(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'no'
        })
        self.assertEqual(0, values[1].value)

    def test_expression_match(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'yes'
        })
        self.assertEqual('mwa-ha-ha', values[2].value)

    def test_expression_nomatch(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'no'
        })
        self.assertEqual('hehe', values[2].value)
