from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch, MagicMock
from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.sql_db.routers import allow_migrate, SYNCLOGS_APP, ICDS_REPORTS_APP

WAREHOUSE_DB = 'warehouse'
db_dict = {'NAME': 'commcarehq_warehouse', 'USER': 'commcarehq', 'HOST': 'hqdb0', 'PORT': 5432}
WAREHOUSE_DATABASE = {
    'default': {},
    WAREHOUSE_DB: db_dict,
}


class AllowMigrateTest(SimpleTestCase):

    @override_settings(
        WAREHOUSE_DATABASE_ALIAS=WAREHOUSE_DB,
        DATABASES=WAREHOUSE_DATABASE,
        USE_PARTITIONED_DATABASE=True,
    )
    def test_warehouse_migrate(self):
        self.assertIs(True, allow_migrate(WAREHOUSE_DB, 'warehouse'))
        with patch('corehq.sql_db.routers.partition_config', MagicMock()):
            self.assertIs(False, allow_migrate(WAREHOUSE_DB, 'couchforms'))
        self.assertIs(False, allow_migrate('default', 'warehouse'))

    @override_settings(
        SYNCLOGS_SQL_DB_ALIAS='default',
        USE_PARTITIONED_DATABASE=False,
        DATABASES={
            'default': {},
            'synclogs': {
                'NAME': 'commcarehq_synclogs',
                'USER': 'commcarehq',
                'HOST': 'hqdb0', 'PORT': 5432
            },
        }
    )
    def test_synclogs_default(self):
        self.assertIs(True, allow_migrate('default', SYNCLOGS_APP))
        self.assertIs(False, allow_migrate('synclogs', SYNCLOGS_APP))

    @override_settings(
        SYNCLOGS_SQL_DB_ALIAS='synclogs',
        USE_PARTITIONED_DATABASE=True,
        DATABASES={
            'default': {},
            'synclogs': {
                'NAME': 'commcarehq_synclogs',
                'USER': 'commcarehq',
                'HOST': 'hqdb0', 'PORT': 5432
            },
        }
    )
    def test_synclogs_db(self):
        self.assertIs(False, allow_migrate('default', SYNCLOGS_APP))
        self.assertIs(True, allow_migrate('synclogs', SYNCLOGS_APP))

    @patch('corehq.sql_db.routers.get_icds_ucr_db_alias')
    def test_icds_db(self, mock):
        mock.return_value = None
        self.assertIs(False, allow_migrate('default', ICDS_REPORTS_APP))
        mock.return_value = 'icds'
        self.assertIs(False, allow_migrate('default', ICDS_REPORTS_APP))
        self.assertIs(True, allow_migrate('icds', ICDS_REPORTS_APP))

    @patch('corehq.sql_db.routers.get_icds_ucr_citus_db_alias')
    def test_icds_db_citus(self, mock):
        mock.return_value = None
        self.assertIs(False, allow_migrate('default', ICDS_REPORTS_APP))
        mock.return_value = 'icds'
        self.assertIs(False, allow_migrate('default', ICDS_REPORTS_APP))
        self.assertIs(True, allow_migrate('icds', ICDS_REPORTS_APP))

    def test_synclogs_non_partitioned(self):
        self.assertIs(False, allow_migrate('synclogs', 'accounting'))
        self.assertIs(True, allow_migrate(None, 'accounting'))
        self.assertIs(True, allow_migrate('default', 'accounting'))
