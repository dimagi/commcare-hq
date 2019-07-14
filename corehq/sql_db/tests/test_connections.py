from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import mock
from collections import Counter

from django.test import override_settings
from django.test.testcases import SimpleTestCase

from corehq.sql_db.connections import ConnectionManager
from corehq.sql_db.util import filter_out_stale_standbys
from six.moves import range


def _get_db_config(db_name):
    return {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': db_name,
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
        'HQ_ACCEPTABLE_STANDBY_DELAY': 3
    }


DATABASES = {
    'default': _get_db_config('default'),
    'ucr': _get_db_config('ucr'),
    'other': _get_db_config('other')
}
REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default'
}


@override_settings(DATABASES=DATABASES, REPORTING_DATABASES=REPORTING_DATABASES)
class ConnectionManagerTests(SimpleTestCase):
    @override_settings(UCR_DATABASE_URL='ucr-url', REPORTING_DATABASES=None)
    def test_legacy_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'ucr-url'
        })

    @override_settings(REPORTING_DATABASES={})
    def test_new_settings_empty(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/default'
        })

    @override_settings(REPORTING_DATABASES={'default': 'default', 'ucr': 'ucr', 'other': 'other'})
    def test_new_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/ucr',
            'other': 'postgresql+psycopg2://:@localhost:5432/other'
        })

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', return_value=0)
    def test_read_load_balancing(self, *args):
        reporting_dbs = {
            'ucr': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1), ('default', 1)]
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            manager = ConnectionManager()
            self.assertEqual(manager.db_connection_map, {
                'default': 'postgresql+psycopg2://:@localhost:5432/default',
                'ucr': 'postgresql+psycopg2://:@localhost:5432/ucr',
                'other': 'postgresql+psycopg2://:@localhost:5432/other'
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

        with override_settings(REPORTING_DATABASES={'default': 'default'}):
            manager = ConnectionManager()
            self.assertEqual(
                ['default', 'default', 'default'],
                [manager.get_load_balanced_read_db_alias('default') for i in range(3)]
            )

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', lambda x, y: {'ucr': 4}.get(x, 0))
    def test_standby_filtering(self, *args):
        reporting_dbs = {
            'ucr_engine': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1)]
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            # should always return the `other` db since `ucr` has bad replication delay
            manager = ConnectionManager()
            self.assertEqual(
                ['other', 'other', 'other'],
                [manager.get_load_balanced_read_db_alias('ucr_engine') for i in range(3)]
            )

    @mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', return_value=0)
    def test_load_balanced_read_apps(self, mock):
        load_balanced_apps = {
            'users': [
                ('users_db1', 5),
            ]
        }

        with override_settings(
            LOAD_BALANCED_APPS=load_balanced_apps,
            DATABASES = {
                'default': _get_db_config('default'),
                'users_db1': _get_db_config('users_db1')}):
            manager = ConnectionManager()
            self.assertEqual(
                manager.get_load_balanced_read_db_alias('users', default="default_option"),
                'users_db1'
            )

        with override_settings(LOAD_BALANCED_APPS=load_balanced_apps):
            # load_balanced_db should be part of settings.DATABASES
            with self.assertRaises(AssertionError):
                ConnectionManager().get_load_balanced_read_db_alias('users')


        # If `LOAD_BALANCED_APPS` is not set for an app, it should point to default kwarg
        manager = ConnectionManager()
        self.assertEqual(
            manager.get_load_balanced_read_db_alias('users', default='default_option'),
            'default_option'
        )

    def test_filter_out_stale_standbys(self, *args):
        with mock.patch('corehq.sql_db.util.get_replication_delay_for_standby', lambda x, y: {'ucr': 2, 'default': 4}.get(x, 0)):
            self.assertEqual(
                filter_out_stale_standbys(['ucr', 'default']),
                ['ucr']
            )
