from collections import Counter

from django.test import override_settings
from django.test.testcases import SimpleTestCase

from corehq.sql_db.connections import ConnectionManager


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
    @override_settings(UCR_DATABASE_URL='ucr-url', REPORTING_DATABASES=None, REPORTING_ENGINES=None)
    def test_legacy_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'ucr-url',
        })

    @override_settings(REPORTING_DATABASES={}, REPORTING_ENGINES=None)
    def test_new_settings_empty(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/default',
        })

    def test_new_settings(self):
        engine_conf = {'default': 'default', 'ucr': 'ucr', 'other': 'other'}
        variations = [
            {'REPORTING_DATABASES': engine_conf, 'REPORTING_ENGINES': None},
            {'REPORTING_DATABASES': {}, 'REPORTING_ENGINES': engine_conf},
            {'REPORTING_DATABASES': DATABASES, 'REPORTING_ENGINES': engine_conf},
        ]
        for settings_variation in variations:
            with override_settings(**settings_variation):
                self._check_connnection_map()

    def _check_connnection_map(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/ucr',
            'other': 'postgresql+psycopg2://:@localhost:5432/other',
        })
        return manager

    def test_read_load_balancing(self):
        reporting_dbs = {
            'ucr': {
                'WRITE': 'ucr',
                'READ': [('ucr', 8), ('other', 1), ('default', 1)]
            },
        }

        def _test_load_balancing():
            manager = self._check_connnection_map()

            # test that load balancing works with a 10% margin for randomness
            total_requests = 10000
            randomness_margin = total_requests * 0.1
            total_weighting = sum(db[1] for db in reporting_dbs['ucr']['READ'])
            expected = {
                alias: weight * total_requests / total_weighting
                for alias, weight in reporting_dbs['ucr']['READ']
            }
            balanced = Counter(manager.get_load_balanced_read_engine_id('ucr') for i in range(total_requests))
            for db, requests in balanced.items():
                self.assertAlmostEqual(requests, expected[db], delta=randomness_margin)

        with override_settings(REPORTING_DATABASES=reporting_dbs, REPORTING_ENGINES=None):
            _test_load_balancing()

        with override_settings(REPORTING_DATABASES=DATABASES, REPORTING_ENGINES=reporting_dbs):
            _test_load_balancing()

        with override_settings(REPORTING_DATABASES={'default': 'default'}, REPORTING_ENGINES=None):
            manager = ConnectionManager()
            self.assertEqual(
                ['default', 'default', 'default'],
                [manager.get_load_balanced_read_engine_id('default') for i in range(3)]
            )

        with override_settings(
                REPORTING_DATABASES={'default': _get_db_config('default')},
                REPORTING_ENGINES={'default': 'default'}
        ):
            manager = ConnectionManager()
            self.assertEqual(
                ['default', 'default', 'default'],
                [manager.get_load_balanced_read_engine_id('default') for i in range(3)]
            )
