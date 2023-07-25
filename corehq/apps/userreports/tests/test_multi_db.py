import uuid
from contextlib import ExitStack

from django.db import DEFAULT_DB_ALIAS
from django.test import TestCase

from unittest.mock import patch

from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.sql.adapter import MultiDBSqlAdapter
from corehq.apps.userreports.tests.utils import (
    doc_to_change,
    get_sample_data_source,
    get_sample_doc_and_indicators,
    get_sample_report_config,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.case import get_case_pillow
from corehq.sql_db import connections
from corehq.sql_db.connections import DEFAULT_ENGINE_ID
from corehq.sql_db.tests.utils import temporary_database
from corehq.util.test_utils import flag_enabled


@flag_enabled('ENABLE_UCR_MIRRORS')
class UCRMultiDBTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(UCRMultiDBTest, cls).setUpClass()
        cls.db2_name = 'cchq_ucr_tests'
        default_db_url = connections.connection_manager.get_connection_string(DEFAULT_DB_ALIAS)
        db_conn_parts = default_db_url.split('/')
        db_conn_parts[-1] = cls.db2_name
        cls.db2_url = '/'.join(db_conn_parts)

        cls.context_managers = ExitStack()
        cls.context_managers.enter_context(connections.override_engine('engine-1', default_db_url, 'default'))
        cls.context_managers.enter_context(connections.override_engine('engine-2', cls.db2_url, cls.db2_name))

        # setup data sources
        data_source_template = get_sample_data_source()
        cls.ds_1 = DataSourceConfiguration.wrap(data_source_template.to_json())
        cls.ds_1.engine_id = 'engine-1'
        cls.ds_1.save()
        cls.ds_2 = DataSourceConfiguration.wrap(data_source_template.to_json())
        cls.ds_2.engine_id = 'engine-2'
        cls.ds_2.save()

        cls.context_managers.enter_context(temporary_database(cls.db2_name))

        cls.ds1_adapter = get_indicator_adapter(cls.ds_1)
        cls.ds2_adapter = get_indicator_adapter(cls.ds_2)

    def setUp(self):
        # initialize the tables
        self.ds1_adapter.rebuild_table()
        self.ds2_adapter.rebuild_table()
        self.assertEqual(0, self.ds1_adapter.get_query_object().count())
        self.assertEqual(0, self.ds2_adapter.get_query_object().count())

    @classmethod
    def tearDownClass(cls):
        # delete data sources
        cls.ds_1.delete()
        cls.ds_2.delete()

        # dispose secondary engine
        cls.ds2_adapter.session_helper.engine.dispose()

        cls.context_managers.__exit__(None, None, None)
        super(UCRMultiDBTest, cls).tearDownClass()

    def tearDown(self):
        self.ds1_adapter.session_helper.Session.remove()
        self.ds2_adapter.session_helper.Session.remove()
        self.ds1_adapter.drop_table()
        self.ds2_adapter.drop_table()

    def test_patches_and_setup(self):
        self.assertEqual(connections.connection_manager.get_connection_string(DEFAULT_DB_ALIAS),
                         connections.connection_manager.get_connection_string('engine-1'))
        self.assertEqual(self.db2_url,
                         connections.connection_manager.get_connection_string('engine-2'))

        self.assertNotEqual(str(self.ds1_adapter.engine.url), str(self.ds2_adapter.engine.url))
        self.assertEqual(connections.connection_manager.get_connection_string(DEFAULT_DB_ALIAS),
                         str(self.ds1_adapter.engine.url))
        self.assertEqual(self.db2_url, str(self.ds2_adapter.engine.url))

    def test_pillow_save_to_multiple_databases(self):
        self.assertNotEqual(self.ds1_adapter.engine.url, self.ds2_adapter.engine.url)
        pillow = get_case_pillow(ucr_configs=[self.ds_1, self.ds_2])
        self.assertNotEqual(self.ds1_adapter.engine.url, self.ds2_adapter.engine.url)
        sample_doc, _ = get_sample_doc_and_indicators()
        pillow.process_change(doc_to_change(sample_doc))
        self.assertNotEqual(self.ds1_adapter.engine.url, self.ds2_adapter.engine.url)
        self.assertEqual(1, self.ds1_adapter.get_query_object().count())
        self.assertEqual(1, self.ds2_adapter.get_query_object().count())

    def test_pillow_save_to_one_database_at_a_time(self):
        pillow = get_case_pillow(ucr_configs=[self.ds_1])

        sample_doc, _ = get_sample_doc_and_indicators()
        pillow.process_change(doc_to_change(sample_doc))

        self.assertEqual(1, self.ds1_adapter.get_query_object().count())
        self.assertEqual(0, self.ds2_adapter.get_query_object().count())

        # save to the other
        pillow = get_case_pillow(ucr_configs=[self.ds_2])
        orig_id = sample_doc['_id']
        sample_doc['_id'] = uuid.uuid4().hex
        pillow.process_change(doc_to_change(sample_doc))
        self.assertEqual(1, self.ds1_adapter.get_query_object().count())
        self.assertEqual(1, self.ds2_adapter.get_query_object().count())
        self.assertEqual(1, self.ds1_adapter.get_query_object().filter_by(doc_id=orig_id).count())
        self.assertEqual(1, self.ds2_adapter.get_query_object().filter_by(doc_id=sample_doc['_id']).count())

    def test_report_data_source(self):
        # bootstrap report data sources against indicator data sources
        report_config_template = get_sample_report_config()
        report_config_1 = ReportConfiguration.wrap(report_config_template.to_json())
        report_config_1.config_id = self.ds_1._id
        report_config_2 = ReportConfiguration.wrap(report_config_template.to_json())
        report_config_2.config_id = self.ds_2._id

        # save a few docs to ds 1
        sample_doc, _ = get_sample_doc_and_indicators()
        num_docs = 3
        for i in range(num_docs):
            sample_doc['_id'] = uuid.uuid4().hex
            self.ds1_adapter.save(sample_doc)

        # ds 1 should have data, ds2 should not
        ds1_rows = ConfigurableReportDataSource.from_spec(report_config_1).get_data()
        self.assertEqual(1, len(ds1_rows))
        self.assertEqual(num_docs, ds1_rows[0]['count'])
        ds2_rows = ConfigurableReportDataSource.from_spec(report_config_2).get_data()
        self.assertEqual(0, len(ds2_rows), ds2_rows)

        # save one doc to ds 2
        sample_doc['_id'] = uuid.uuid4().hex
        self.ds2_adapter.save(sample_doc)

        # ds 1 should still have same data, ds2 should now have one row
        ds1_rows = ConfigurableReportDataSource.from_spec(report_config_1).get_data()
        self.assertEqual(1, len(ds1_rows))
        self.assertEqual(num_docs, ds1_rows[0]['count'])
        ds2_rows = ConfigurableReportDataSource.from_spec(report_config_2).get_data()
        self.assertEqual(1, len(ds2_rows))
        self.assertEqual(1, ds2_rows[0]['count'])

    def test_mirroring(self):
        ds3 = DataSourceConfiguration.wrap(get_sample_data_source().to_json())
        ds3.engine_id = DEFAULT_ENGINE_ID
        ds3.mirrored_engine_ids = ['engine-2']
        adapter = get_indicator_adapter(ds3)
        self.assertEqual(type(adapter.adapter), MultiDBSqlAdapter)
        self.assertEqual(len(adapter.all_adapters), 2)
        for db_adapter in adapter.all_adapters:
            with db_adapter.session_context() as session:
                self.assertEqual(0, session.query(db_adapter.get_table()).count())

        with (
            patch('pillowtop.models.KafkaCheckpoint.get_or_create_for_checkpoint_id'),
            patch('corehq.apps.userreports.pillow_utils._is_datasource_active', return_value=True)
        ):
            pillow = get_case_pillow(ucr_configs=[ds3])
        sample_doc, _ = get_sample_doc_and_indicators()
        pillow.process_change(doc_to_change(sample_doc))

        for db_adapter in adapter.all_adapters:
            with db_adapter.session_context() as session:
                self.assertEqual(1, session.query(db_adapter.get_table()).count())
