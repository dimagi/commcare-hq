import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from freezegun import freeze_time
from jsonobject.exceptions import BadValueError

from corehq.apps.domain.models import AllowedUCRExpressionSettings
from corehq.apps.userreports.const import (
    UCR_NAMED_EXPRESSION,
    UCR_NAMED_FILTER,
)
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    UCRExpression,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
    get_sample_doc_and_indicators,
)
from corehq.sql_db.connections import UCR_ENGINE_ID
from corehq.util.test_utils import flag_enabled


class TestDataSourceConfigAllowedExpressionsValidation(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        AllowedUCRExpressionSettings.save_allowed_ucr_expressions('domain_nopermission', [])
        AllowedUCRExpressionSettings.save_allowed_ucr_expressions('domain_baseitem', ['base_item_expression'])
        AllowedUCRExpressionSettings.save_allowed_ucr_expressions('domain_related_doc', ['related_doc'])
        AllowedUCRExpressionSettings.save_allowed_ucr_expressions(
            'domain_both',
            ['related_doc', 'base_item_expression']
        )
        cls.config = get_sample_data_source()
        cls.config = cls.config.to_json()
        cls.config['configured_indicators'].append({
            "type": "expression",
            "is_primary_key": False,
            "is_nullable": True,
            "datatype": "string",
            "expression": {
                "value_expression": {
                    "datatype": None,
                    "type": "property_name",
                    "property_name": "name"
                },
                "type": "related_doc",
                "related_doc_type": "Location",
                "doc_id_expression": {
                    "datatype": None,
                    "type": "property_name",
                    "property_name": "health_post_id"
                }
            },
            "column_id": "health_post_name"
        })
        cls.config['base_item_expression'] = {
            "datatype": None,
            "property_name": "actions",
            "type": "property_name"
        }
        cls.config = DataSourceConfiguration.wrap(cls.config)
        return super().setUpClass()

    def test_raises_when_domain_has_no_permission(self):
        self.config.domain = 'domain_nopermission'
        err_msg = f'base_item_expression is not allowed for domain {self.config.domain}'
        with self.assertRaisesMessage(BadSpecError, err_msg):
            self.config.validate()

    def test_raises_when_related_doc_used_without_permission(self):
        self.config.domain = 'domain_baseitem'
        err_msg = f'related_doc is not allowed for domain {self.config.domain}'
        with self.assertRaisesMessage(BadSpecError, err_msg):
            self.config.validate()

    def test_raises_when_domain_has_only_related_doc(self):
        self.config.domain = 'domain_related_doc'
        err_msg = f'base_item_expression is not allowed for domain {self.config.domain}'
        with self.assertRaisesMessage(BadSpecError, err_msg):
            self.config.validate()

    def test_does_not_raise_with_permissions(self):
        self.config.domain = 'domain_both'
        self.assertIsNone(self.config.validate())

    def test_allows_domains_with_no_explicit_permissions(self):
        self.config.domain = 'random_domain'
        self.assertIsNone(self.config.validate())


@patch('corehq.apps.userreports.models.AllowedUCRExpressionSettings.disallowed_ucr_expressions', MagicMock(return_value=[]))
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


class DataSourceConfigurationTests(TestCase):

    def test_by_domain_returns_relevant_datasource_configs(self):
        results = DataSourceConfiguration.by_domain('foo')
        self.assertEqual(len(results), 2)
        self.assertEqual({r.table_id for r in results}, {'foo1', 'foo2'})

    def test_by_domain_returns_empty_list(self):
        results = DataSourceConfiguration.by_domain('not-foo')
        self.assertEqual(results, [])

    def test_all(self):
        results = list(DataSourceConfiguration.all())
        self.assertEqual(len(results), 3)
        self.assertEqual({r.table_id for r in results},
                         {'foo1', 'foo2', 'bar1'})

    def test_last_modified_date_updates_successfully(self):
        initial_date = datetime.datetime(2020, 1, 1)
        with freeze_time(initial_date) as frozen_time:
            datasource = DataSourceConfiguration(
                domain='mod-test', table_id='mod-test',
                referenced_doc_type='XFormInstance')
            datasource.save()
            self.addCleanup(datasource.delete)

            previous_modified_date = datasource.last_modified
            frozen_time.tick(delta=datetime.timedelta(hours=1))
            datasource.save()

        self.assertGreater(datasource.last_modified, previous_modified_date)

    def test_create_requires_domain(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(table_id='table',
                                    referenced_doc_type='XFormInstance').save()

    def test_create_requires_table_id(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain',
                                    referenced_doc_type='XFormInstance').save()

    def test_create_requires_doc_type(self):
        with self.assertRaises(BadValueError):
            DataSourceConfiguration(domain='domain', table_id='table').save()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for domain, table_id in [('foo', 'foo1'), ('foo', 'foo2'),
                                 ('bar', 'bar1')]:
            config = DataSourceConfiguration(
                domain=domain,
                table_id=table_id,
                referenced_doc_type='XFormInstance')
            config.save()
            cls.addClassCleanup(config.delete)


@patch('corehq.apps.userreports.models.AllowedUCRExpressionSettings.disallowed_ucr_expressions', MagicMock(return_value=[]))
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
                            'type': 'named',
                            'name': 'is_evil',
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


class TestDBExpressions(TestCase):

    @flag_enabled('UCR_EXPRESSION_REGISTRY')
    def test_named_db_expression(self):
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
                }
            },
            'named_filters': {},
            'configured_filter': {},
            'configured_indicators': [
                {
                    "type": "expression",
                    "column_id": "laugh_sound",
                    "datatype": "string",
                    "expression": {
                        'type': 'named',
                        'name': 'laugh_sound_db'  # note not in the named_expressions list above
                    }
                }
            ]
        })

        UCRExpression.objects.create(
            name='laugh_sound_db',
            domain='test',
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
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
            },
        )

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

    @flag_enabled('UCR_EXPRESSION_REGISTRY')
    def test_named_db_filter(self):
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
                }
            },
            'configured_filter': {
                'type': 'and',
                'filters': [
                    {
                        'type': 'named',
                        'name': 'pregnant',
                    },
                    {
                        'type': 'named',
                        'name': 'age_db',  # Note that this isn't in the list of `named_filters` above
                    }
                ]
            },
            'configured_indicators': []
        })
        UCRExpression.objects.create(
            name='age_db',
            domain='test',
            expression_type=UCR_NAMED_FILTER,
            definition={
                'type': 'property_match',
                'property_name': 'age',
                'property_value': 34,
            },
        )

        self.assertTrue(self.indicator_configuration.filter({
            'doc_type': 'CommCareCase',
            'domain': 'test',
            'type': 'ttc_mother',
            'mother_state': 'pregnant',
            'age': 34,
        }))
