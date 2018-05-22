from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from collections import Counter

from django.test import override_settings
from django.test.testcases import SimpleTestCase

from corehq.sql_db.connections import ConnectionManager
from six.moves import range


def _get_db_config(db_name):
    return {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': db_name,
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
    }


DATABASES = {
    'default': _get_db_config('default'),
    'ucr': _get_db_config('ucr'),
    'other': _get_db_config('other')
}


@override_settings(DATABASES=DATABASES)
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

    def test_read_load_balancing(self):
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
            balanced = Counter(manager.get_load_balanced_read_engine_id('ucr') for i in range(total_requests))
            for db, requests in balanced.items():
                self.assertAlmostEqual(requests, expected[db], delta=randomness_margin)

        with override_settings(REPORTING_DATABASES={'default': 'default'}):
            manager = ConnectionManager()
            self.assertEqual(
                ['default', 'default', 'default'],
                [manager.get_load_balanced_read_engine_id('default') for i in range(3)]
            )
