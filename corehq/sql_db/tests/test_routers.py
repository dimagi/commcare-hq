from __future__ import absolute_import
from mock import patch, MagicMock
from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.sql_db.routers import allow_migrate


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
        self.assertTrue(allow_migrate(WAREHOUSE_DB, 'warehouse'))
        with patch('corehq.sql_db.routers.partition_config', MagicMock()):
            self.assertFalse(allow_migrate(WAREHOUSE_DB, 'couchforms'))
        self.assertFalse(allow_migrate('default', 'warehouse'))
