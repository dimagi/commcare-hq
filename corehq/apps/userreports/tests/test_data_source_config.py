from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import time
from mock import patch
from django.test import SimpleTestCase, TestCase
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators
from corehq.sql_db.connections import UCR_ENGINE_ID


class DataSourceConfigurationTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_data_source()

    def test_metadata(self):
        # metadata
        self.assertEqual('user-reports', self.config.domain)
        self.assertEqual('CommCareCase', self.config.referenced_doc_type)
        self.assertEqual('CommBugz', self.config.display_name)
        self.assertEqual('sample', self.config.table_id)
        self.assertEqual(UCR_ENGINE_ID, self.config.engine_id)

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
            'inserted_at',
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

    @patch('corehq.apps.userreports.specs.datetime')
    def test_indicators(self, datetime_mock):
        fake_time_now = datetime.datetime(2015, 4, 24, 12, 30, 8, 24886)
        datetime_mock.utcnow.return_value = fake_time_now
        # indicators
        sample_doc, expected_indicators = get_sample_doc_and_indicators(fake_time_now)
        [results] = self.config.get_all_values(sample_doc)
        for result in results:
            try:
                self.assertEqual(expected_indicators[result.column.id], result.value)
            except AssertionError:
                # todo: this is a hack due to the fact that type conversion currently happens
                # in the database layer. this should eventually be fixed.
                self.assertEqual(str(expected_indicators[result.column.id]), result.value)

    def test_configured_filter_auto_date_convert(self):
        source = self.config.to_json()
        source['configured_filter'] = {
            "expression": {
                "datatype": "date",
                "expression": {
                    "datatype": "date",
                    "property_name": "visit_date",
                    "type": "property_name"
                },
                "type": "root_doc"
            },
            "operator": "gt",
            "property_value": "2015-05-05",
            "type": "boolean_expression"
        }
        config = DataSourceConfiguration.wrap(source)
        config.validate()

    def test_duplicate_columns(self):
        bad_config = DataSourceConfiguration.wrap(self.config.to_json())
        bad_config.configured_indicators.append(bad_config.configured_indicators[-1])
        with self.assertRaises(BadSpecError):
            bad_config.validate()


class DataSourceFilterInterpolationTest(SimpleTestCase):
    def _setup_config(self, doc_type, filter_):
        return DataSourceConfiguration(
            domain='test',
            referenced_doc_type=doc_type,
            table_id='blah',
            configured_filter=filter_
        )

    def _case_config(self, filter_):
        return self._setup_config('CommCareCase', filter_)

    def _form_config(self, filter_):
        return self._setup_config('XFormInstance', filter_)

    def _test_helper(self, data_source, expected_filter):
        self.assertEqual(
            data_source.get_case_type_or_xmlns_filter(),
            expected_filter
        )

    def test_one_case_type(self):
        self._test_helper(
            self._case_config({
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "operator": "eq",
                "property_value": "ticket"
            }),
            ['ticket']
        )

    def test_multiple_case_type(self):
        self._test_helper(
            self._case_config({
                "type": "boolean_expression",
                "operator": "in",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": ["ticket", "task"]
            }),
            ["ticket", "task"]
        )

    def test_one_xmlns(self):
        self._test_helper(
            self._form_config({
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns"
                },
                "property_value": "xmlns"
            }),
            ['xmlns']
        )

    def test_multiple_xmlns(self):
        self._test_helper(
            self._form_config({
                "type": "boolean_expression",
                "operator": "in",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns"
                },
                "property_value": ["xmlns1", "xmlns2"]
            }),
            ["xmlns1", "xmlns2"]
        )

    def test_xmlns_with_and(self):
        self._test_helper(
            self._form_config({
                "type": "and",
                "filters": [
                    {
                        "type": "boolean_expression",
                        "operator": "eq",
                        "expression": {
                            "type": "property_name",
                            "property_name": "xmlns"
                        },
                        "property_value": "xmlns"
                    }
                ]
            }),
            ["xmlns"]
        )

    def test_case_type_with_and(self):
        self._test_helper(
            self._case_config({
                "type": "and",
                "filters": [
                    {
                        "type": "boolean_expression",
                        "operator": "eq",
                        "expression": {
                            "type": "property_name",
                            "property_name": "type"
                        },
                        "property_value": "ticket"
                    }
                ]
            }),
            ["ticket"]
        )

    def test_case_type_with_and_other_filter(self):
        self._test_helper(
            self._case_config({
                "type": "and",
                "filters": [
                    {
                        "type": "boolean_expression",
                        "operator": "eq",
                        "expression": {
                            "type": "property_name",
                            "property_name": "type"
                        },
                        "property_value": "ticket"
                    },
                    {
                        "type": "boolean_expression",
                        "operator": "eq",
                        "expression": {
                            "type": "property_name",
                            "property_name": "other_property"
                        },
                        "property_value": "not_ticket"
                    }
                ]
            }),
            ["ticket"]
        )

    def test_invalid_expression(self):
        self._test_helper(
            self._form_config({
                "operator": "eq",
                "type": "boolean_expression",
                "expression": 1,
                "property_value": 2
            }),
            [None]
        )


class DataSourceConfigurationDbTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DataSourceConfigurationDbTest, cls).setUpClass()

        # TODO - handle cleanup appropriately so this isn't needed
        for data_source_config in DataSourceConfiguration.all():
            data_source_config.delete()

        DataSourceConfiguration(domain='foo', table_id='foo1', referenced_doc_type='XFormInstance').save()
        DataSourceConfiguration(domain='foo', table_id='foo2', referenced_doc_type='XFormInstance').save()
        DataSourceConfiguration(domain='bar', table_id='bar1', referenced_doc_type='XFormInstance').save()

    @classmethod
    def tearDownClass(cls):
        for config in DataSourceConfiguration.all():
            config.delete()
        super(DataSourceConfigurationDbTest, cls).tearDownClass()

    def test_get_by_domain(self):
        results = DataSourceConfiguration.by_domain('foo')
        self.assertEqual(2, len(results))
        for item in results:
            self.assertTrue(item.table_id in ('foo1', 'foo2'))

        results = DataSourceConfiguration.by_domain('not-foo')
        self.assertEqual(0, len(results))

    def test_last_modified_date(self):
        start = datetime.datetime.utcnow()
        time.sleep(.01)
        data_source = DataSourceConfiguration(
            domain='mod-test', table_id='mod-test', referenced_doc_type='XFormInstance'
        )
        data_source.save()
        self.assertTrue(start < data_source.last_modified)
        time.sleep(.01)
        between = datetime.datetime.utcnow()
        self.assertTrue(between > data_source.last_modified)
        time.sleep(.01)
        data_source.save()
        time.sleep(.01)
        self.assertTrue(between < data_source.last_modified)
        self.assertTrue(datetime.datetime.utcnow() > data_source.last_modified)

    def test_get_all(self):
        self.assertEqual(3, len(list(DataSourceConfiguration.all())))

    def test_domain_is_required(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(table_id='table',
                                    referenced_doc_type='XFormInstance').save()

    def test_table_id_is_required(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain',
                                    referenced_doc_type='XFormInstance').save()

    def test_doc_type_is_required(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain', table_id='table').save()


class IndicatorNamedExpressionTest(SimpleTestCase):

    def setUp(self):
        self.indicator_configuration = DataSourceConfiguration.wrap({
            'display_name': 'Mother Indicators',
            'doc_type': 'DataSourceConfiguration',
            'domain': 'test',
            'referenced_doc_type': 'CommCareCase',
            'table_id': 'mother_indicators',
            'named_expressions': {
                'pregnant': {
                    'type': 'property_name',
                    'property_name': 'pregnant',
                },
                'is_evil': {
                    'type': 'property_name',
                    'property_name': 'is_evil',
                },
                'laugh_sound': {
                    'type': 'conditional',
                    'test': {
                        'type': 'boolean_expression',
                        'expression': {
                            'type': 'property_name',
                            'property_name': 'is_evil',
                        },
                        'operator': 'eq',
                        'property_value': True,
                    },
                    'expression_if_true': "mwa-ha-ha",
                    'expression_if_false': "hehe",
                }
            },
            'named_filters': {},
            'configured_filter': {
                'type': 'boolean_expression',
                'expression': {
                    'type': 'named',
                    'name': 'pregnant'
                },
                'operator': 'eq',
                'property_value': 'yes',
            },
            'configured_indicators': [
                {
                    "type": "expression",
                    "column_id": "laugh_sound",
                    "datatype": "string",
                    "expression": {
                        'type': 'named',
                        'name': 'laugh_sound'
                    }
                },
                {
                    "type": "expression",
                    "column_id": "characterization",
                    "datatype": "string",
                    "expression": {
                        'type': 'conditional',
                        'test': {
                            'type': 'boolean_expression',
                            'expression': {
                                'type': 'named',
                                'name': 'is_evil',
                            },
                            'operator': 'eq',
                            'property_value': True,
                        },
                        'expression_if_true': "evil!",
                        'expression_if_false': "okay",
                    }
                },

            ]
        })

    def test_named_expressions_serialization(self):
        # in response to http://manage.dimagi.com/default.asp?244625
        self.assertNotEqual({}, self.indicator_configuration.to_json()['named_expressions'])

    def test_filter_match(self):
        self.assertTrue(self.indicator_configuration.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'pregnant': 'yes'
        }))

    def test_filter_nomatch(self):
        self.assertFalse(self.indicator_configuration.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'pregnant': 'no'
        }))

    def test_indicator(self):
        for evil_status, laugh in ((True, 'mwa-ha-ha'), (False, 'hehe')):
            [values] = self.indicator_configuration.get_all_values({
                'doc_type': 'CommCareCase',
                'domain': 'test',
                'pregnant': 'yes',
                'is_evil': evil_status
            })
            i = 2
            self.assertEqual('laugh_sound', values[i].column.id)
            self.assertEqual(laugh, values[i].value)

    def test_nested_indicator(self):
        for evil_status, characterization in ((True, 'evil!'), (False, 'okay')):
            [values] = self.indicator_configuration.get_all_values({
                'doc_type': 'CommCareCase',
                'domain': 'test',
                'pregnant': 'yes',
                'is_evil': evil_status
            })
            i = 3
            self.assertEqual('characterization', values[i].column.id)
            self.assertEqual(characterization, values[i].value)

    def test_missing_reference(self):
        bad_config = DataSourceConfiguration.wrap(self.indicator_configuration.to_json())
        bad_config.configured_indicators.append({
            "type": "expression",
            "column_id": "missing",
            "datatype": "string",
            "expression": {
                'type': 'named',
                'name': 'missing'
            }
        })
        with self.assertRaises(BadSpecError):
            bad_config.validate()

    def test_no_self_lookups(self):
        bad_config = DataSourceConfiguration.wrap(self.indicator_configuration.to_json())
        bad_config.named_expressions['broken'] = {
            "type": "named",
            "name": "broken",
        }
        with self.assertRaises(BadSpecError):
            bad_config.validate()

    def test_no_recursive_lookups(self):
        bad_config = DataSourceConfiguration.wrap(self.indicator_configuration.to_json())
        bad_config.named_expressions['broken'] = {
            "type": "named",
            "name": "also_broken",
        }
        bad_config.named_expressions['also_broken'] = {
            "type": "named",
            "name": "broken",
        }
        with self.assertRaises(BadSpecError):
            bad_config.validate()

    def test_no_pk_attribute(self):
        bad_config = DataSourceConfiguration.wrap(self.indicator_configuration.to_json())
        bad_config.sql_settings.primary_key = ['doc_id', 'laugh_sound']
        with self.assertRaises(BadSpecError):
            bad_config.validate()

    def test_missing_pk_column(self):
        bad_config = DataSourceConfiguration.wrap(self.indicator_configuration.to_json())
        bad_config.sql_settings.primary_key = ['doc_id', 'no_exist']
        with self.assertRaises(BadSpecError):
            bad_config.validate()


class IndicatorNamedFilterTest(SimpleTestCase):

    def setUp(self):
        self.indicator_configuration = DataSourceConfiguration.wrap({
            'display_name': 'Mother Indicators',
            'doc_type': 'DataSourceConfiguration',
            'domain': 'test',
            'referenced_doc_type': 'CommCareCase',
            'table_id': 'mother_indicators',
            'named_expressions': {
                'on_a_date': {
                    'type': 'property_name',
                    'property_name': 'on_date',
                }
            },
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
                },
                'has_alibi': {
                    'type': 'boolean_expression',
                    'expression': {
                        'type': 'named',
                        'name': 'on_a_date'
                    },
                    'operator': 'eq',
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
        # Confirm that 2 is the right values index:
        i = 2
        self.assertEqual('is_evil', values[i].column.id)
        self.assertEqual(1, values[i].value)

    def test_simple_indicator_nomatch(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'no'
        })
        # Confirm that 2 is the right values index:
        i = 2
        self.assertEqual('is_evil', values[i].column.id)
        self.assertEqual(0, values[i].value)

    def test_expression_match(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'yes'
        })
        # Confirm that 3 is the right values index:
        i = 3
        self.assertEqual('laugh_sound', values[i].column.id)
        self.assertEqual('mwa-ha-ha', values[i].value)

    def test_expression_nomatch(self):
        [values] = self.indicator_configuration.get_all_values({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'evil': 'no'
        })
        # Confirm that 3 is the right values index:
        i = 3
        self.assertEqual('laugh_sound', values[i].column.id)
        self.assertEqual('hehe', values[i].value)
