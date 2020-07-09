from collections import Counter
from unittest import SkipTest

from django.db import DEFAULT_DB_ALIAS
from django.test import override_settings
from django.test.testcases import SimpleTestCase, TestCase

import mock
from corehq.sql_db.connections import (
    ICDS_UCR_CITUS_ENGINE_ID,
    ConnectionManager,
    connection_manager,
)
from corehq.sql_db.tests.test_partition_config import (
    PARTITION_CONFIG_WITH_STANDBYS,
)
from corehq.sql_db.util import (
    get_acceptible_replication_delays,
    get_databases_for_read_query,
    get_replication_delay_for_shard_standbys,
    get_standbys_with_acceptible_delay,
)
from decorator import contextmanager
from testil import eq


def _get_db_config(db_name, master=None, delay=None):
    config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_name,
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
    }
    if master:
        config['STANDBY'] = {
            'MASTER': master
        }
        if delay:
            config['STANDBY']['ACCEPTABLE_REPLICATION_DELAY'] = delay
    return config


DATABASES = {
    DEFAULT_DB_ALIAS: _get_db_config('default'),
    'ucr': _get_db_config('ucr', 'default', 5),
    'other': _get_db_config('other', 'default')
}
REPORTING_DATABASES = {
    'default': DEFAULT_DB_ALIAS,
    'ucr': DEFAULT_DB_ALIAS
}


@override_settings(DATABASES=DATABASES, REPORTING_DATABASES=REPORTING_DATABASES)
class ConnectionManagerTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        get_acceptible_replication_delays.reset_cache()

    @override_settings(REPORTING_DATABASES={})
    def test_new_settings_empty(self):
        manager = ConnectionManager()
        self.assertEqual(manager.engine_id_django_db_map, {
            'default': 'default',
            'ucr': 'default'
        })

    @override_settings(REPORTING_DATABASES={'default': DEFAULT_DB_ALIAS, 'ucr': 'ucr', 'other': 'other'})
    def test_new_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.engine_id_django_db_map, {
            'default': 'default',
            'ucr': 'ucr',
            'other': 'other'
        })

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', return_value=0)
    @mock.patch('corehq.sql_db.util.get_standby_databases', return_value={'ucr', 'other'})
    def test_read_load_balancing(self, *args):
        reporting_dbs = {
            'ucr': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1), ('default', 1)]
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            manager = ConnectionManager()
            self.assertEqual(manager.engine_id_django_db_map, {
                'default': 'default',
                'ucr': 'ucr',
            })

            # test that load balancing works with a 10% margin for randomness
            total_requests = 10000
            randomness_margin = total_requests * 0.1
            total_weighting = sum(db[1] for db in reporting_dbs['ucr']['READ'])
            expected = {
                alias: weight * total_requests // total_weighting
                for alias, weight in reporting_dbs['ucr']['READ']
            }
            balanced = Counter(manager.get_load_balanced_read_db_alias('ucr') for i in range(total_requests))
            for db, requests in balanced.items():
                self.assertAlmostEqual(requests, expected[db], delta=randomness_margin)

        with override_settings(REPORTING_DATABASES={'default': DEFAULT_DB_ALIAS}):
            manager = ConnectionManager()
            self.assertEqual(
                [DEFAULT_DB_ALIAS] * 3,
                [manager.get_load_balanced_read_db_alias(DEFAULT_DB_ALIAS) for i in range(3)]
            )

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', return_value=0)
    @mock.patch('corehq.sql_db.util.get_standby_databases', return_value={'ucr', 'other'})
    def test_read_load_balancing_session(self, *args):
        reporting_dbs = {
            'ucr': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1), ('default', 1)]
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            manager = ConnectionManager()
            self.assertEqual(manager.engine_id_django_db_map, {
                'default': 'default',
                'ucr': 'ucr',
            })

            urls = {
                manager.get_connection_string(alias)
                for alias, _ in reporting_dbs['ucr']['READ']
            }
            self.assertEqual(len(urls), 3)
            # withing 50 iterations we should have seen all 3 databases at least once
            for i in range(50):
                url = manager.get_session_helper('ucr', readonly=True).url
                if url in urls:
                    urls.remove(url)
                if not urls:
                    break

            if urls:
                self.fail(f'DBs skipped in load balancing: {urls}')

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', lambda x: {'other': 4}[x])
    @mock.patch('corehq.sql_db.util.get_standby_databases', return_value={'other'})
    def test_standby_filtering(self, *args):
        reporting_dbs = {
            'ucr_engine': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1)]
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            # should always return the `ucr` db since `other` has bad replication delay
            manager = ConnectionManager()
            self.assertEqual(
                ['ucr', 'ucr', 'ucr'],
                [manager.get_load_balanced_read_db_alias('ucr_engine') for i in range(3)]
            )

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', lambda x: {'ucr': 6, 'other': 4}[x])
    @mock.patch('corehq.sql_db.util.get_standby_databases', return_value={'ucr', 'other'})
    def test_get_databases_for_read_query_filter(self, *args):
        self.assertEqual(
            get_databases_for_read_query({'ucr', 'other'}),
            set()
        )

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', lambda x: {'ucr': 5, 'other': 3}[x])
    @mock.patch('corehq.sql_db.util.get_standby_databases', return_value={'ucr', 'other'})
    def test_get_databases_for_read_query_pass(self, *args):
        self.assertEqual(
            get_databases_for_read_query({'ucr', 'other'}),
            {'ucr', 'other'}
        )


@override_settings(DATABASES=PARTITION_CONFIG_WITH_STANDBYS)
class TestReadsFromShardStandbys(SimpleTestCase):
    def setUp(self):
        super().setUp()
        get_acceptible_replication_delays.reset_cache()

    def test_get_replication_delay_for_shard_standbys(self):
        with self.mock_standby_delay():
            delays = get_replication_delay_for_shard_standbys()
            eq(delays, {'db1_standby': 1, 'db2_standby': 2})

    def test_get_standbys_with_acceptible_delay(self):
        with self.mock_standby_delay({('db1', 1), ('db2', 4)}):
            dbs = get_standbys_with_acceptible_delay()
        eq(dbs, {'db1_standby'})

    @contextmanager
    def mock_standby_delay(self, replication_results=None):
        rows = replication_results or {('db1', 1), ('db2', 2)}
        standbys = {'db1_standby', 'db2_standby'}
        with mock.patch('corehq.sql_db.util._get_replication_delay_results_from_proxy', return_value=rows), \
                mock.patch('corehq.sql_db.util.plproxy_standby_config') as plproxy_standby_config, \
                mock.patch('corehq.sql_db.util.get_standby_databases', return_value=standbys):

            plproxy_standby_config.form_processing_dbs = ['db1_standby', 'db2_standby']
            yield
