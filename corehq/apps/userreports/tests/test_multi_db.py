import uuid
from django.conf import settings
from django.test import SimpleTestCase
from mock import patch
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.tests import get_sample_data_source
from corehq.apps.userreports.sql import connection
from corehq import db

class UCRMultiDBTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        # setup patches
        cls.engine_id_patch = patch('corehq.apps.userreports.sql.connection.get_engine_id')
        cls.connection_manager_patch = patch('corehq.db.connection_manager')
        mock_engine_id_method = cls.engine_id_patch.start()
        mock_engine_id_method.side_effect = lambda x: x.engine_id

        mock_manager = cls.connection_manager_patch.start()
        def connection_string_for_engine(engine_id):
            if engine_id == 'engine-1':
                return settings.SQL_REPORTING_DATABASE_URL
            else:
                return '{}_2'.format(settings.SQL_REPORTING_DATABASE_URL)
        mock_manager._get_connection_string.side_effect = connection_string_for_engine

        data_source_template = get_sample_data_source()
        cls.ds_1 = DataSourceConfiguration.wrap(data_source_template.to_json())
        cls.ds_1.engine_id = 'engine-1'
        cls.ds_2 = DataSourceConfiguration.wrap(data_source_template.to_json())
        cls.ds_2.engine_id = 'engine-2'

    @classmethod
    def tearDownClass(cls):
        cls.engine_id_patch.stop()
        cls.connection_manager_patch.stop()

    def test_patches(self):
        self.assertEqual('engine-1', connection.get_engine_id(self.ds_1))
        self.assertEqual('engine-2', connection.get_engine_id(self.ds_2))

        self.assertEqual(settings.SQL_REPORTING_DATABASE_URL,
                         db.connection_manager._get_connection_string('engine-1'))
        self.assertEqual('{}_2'.format(settings.SQL_REPORTING_DATABASE_URL),
                         db.connection_manager._get_connection_string('engine-2'))
