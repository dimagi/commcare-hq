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
    @override_settings(SQL_REPORTING_DATABASE_URL='sql-url', UCR_DATABASE_URL='ucr-url', REPORTING_DATABASES=None)
    def test_legacy_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'sql-url',
            'ucr': 'ucr-url',
        })

    @override_settings(REPORTING_DATABASES={})
    def test_new_settings_empty(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/default',
        })

    @override_settings(REPORTING_DATABASES={'default': 'default', 'ucr': 'ucr', 'other': 'other'})
    def test_new_settings(self):
        manager = ConnectionManager()
        self.assertEqual(manager.db_connection_map, {
            'default': 'postgresql+psycopg2://:@localhost:5432/default',
            'ucr': 'postgresql+psycopg2://:@localhost:5432/ucr',
            'other': 'postgresql+psycopg2://:@localhost:5432/other',
        })

    def test_replicas(self):
        reporting_dbs = {
            'ucr': {
                'DJANGO_ALIAS': 'ucr',
                'READ_REPLICAS': ['other', 'default']
            },
        }
        with override_settings(REPORTING_DATABASES=reporting_dbs):
            manager = ConnectionManager()
            self.assertEqual(manager.db_connection_map, {
                'default': 'postgresql+psycopg2://:@localhost:5432/default',
                'ucr': 'postgresql+psycopg2://:@localhost:5432/ucr',
                'other': 'postgresql+psycopg2://:@localhost:5432/other',
            })

            self.assertEqual(
                ['other', 'default', 'other', 'default'],
                [manager.get_read_replica_engine_id('ucr') for i in range(4)]
             )

        with override_settings(REPORTING_DATABASES={'default': 'default'}):
            manager = ConnectionManager()
            self.assertEqual(
                ['default', 'default', 'default'],
                [manager.get_read_replica_engine_id('default') for i in range(3)]
             )
