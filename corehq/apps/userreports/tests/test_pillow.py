import decimal
import uuid
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from pillow_retry.models import PillowError
from corehq.motech.repeaters.models import SQLRepeatRecord
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.userreports.data_source_providers import (
    DynamicDataSourceProvider,
    MockDataSourceProvider,
)
from corehq.apps.userreports.exceptions import StaleRebuildError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.models import (
    AsyncIndicator,
    DataSourceConfiguration,
    InvalidUCRData,
    Validation,
)
from corehq.apps.userreports.pillow import (
    REBUILD_CHECK_INTERVAL,
    ConfigurableReportPillowProcessor,
    ConfigurableReportTableManager,
)
from corehq.apps.userreports.pillow_utils import rebuild_table
from corehq.apps.userreports.tasks import (
    queue_async_indicators,
    rebuild_indicators,
)
from corehq.apps.userreports.tests.utils import (
    doc_to_change,
    get_data_source_with_related_doc_type,
    get_sample_data_source,
    get_sample_doc_and_indicators,
    skip_domain_filter_patch,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.signals import sql_case_post_save
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records
from corehq.motech.repeaters.models import (
    ConnectionSettings,
    DataSourceRepeater,
)
from corehq.motech.repeaters.tests.test_repeater import BaseRepeaterTest
from corehq.pillows.case import get_case_pillow
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import flag_enabled, flaky_slow, softer_assert


def setup_module():
    skip_domain_filter_patch.start()


def teardown_module():
    skip_domain_filter_patch.stop()


def _get_pillow(configs, processor_chunk_size=0):
    pillow = get_case_pillow(processor_chunk_size=processor_chunk_size)
    # overwrite processors since we're only concerned with UCR here
    table_manager = ConfigurableReportTableManager(data_source_providers=[])
    ucr_processor = ConfigurableReportPillowProcessor(
        table_manager
    )
    table_manager.bootstrap(configs)
    pillow.processors = [ucr_processor]
    return pillow


class ConfigurableReportTableManagerTest(SimpleTestCase):

    def test_needs_bootstrap_on_initialization(self):
        table_manager = ConfigurableReportTableManager([MockDataSourceProvider()])
        self.assertTrue(table_manager.needs_bootstrap())

    def test_bootstrap_sets_time(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManager([MockDataSourceProvider()])
        table_manager.bootstrap([])
        after_now = datetime.utcnow() + timedelta(microseconds=1)
        self.assertTrue(table_manager.bootstrapped)
        self.assertTrue(before_now < table_manager.last_bootstrapped)
        self.assertTrue(after_now > table_manager.last_bootstrapped)
        self.assertFalse(table_manager.needs_bootstrap())

    def test_needs_bootstrap_window(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManager([MockDataSourceProvider()])
        table_manager.bootstrap([])
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL - 5)
        self.assertFalse(table_manager.needs_bootstrap())
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL)
        self.assertTrue(table_manager.needs_bootstrap())


class ConfigurableReportTableManagerDbTest(TestCase):
    def tearDown(self):
        for data_source in DynamicDataSourceProvider().get_all_data_sources():
            data_source.get_db().delete_doc(data_source.get_id)

    def test_table_adapters(self):
        data_source_1 = get_sample_data_source()
        ds_1_domain = data_source_1.domain
        data_source_1.save()

        table_manager = ConfigurableReportTableManager([MockDataSourceProvider({
            ds_1_domain: [data_source_1]
        })])
        table_manager.bootstrap()
        self.assertEqual(1, len(table_manager.table_adapters_by_domain))
        self.assertEqual(1, len(table_manager.table_adapters_by_domain[ds_1_domain]))
        self.assertEqual(data_source_1, table_manager.table_adapters_by_domain[ds_1_domain][0].config)

    def test_merge_table_adapters(self):
        data_source_1 = get_sample_data_source()
        data_source_1.save()
        ds_1_domain = data_source_1.domain
        table_manager = ConfigurableReportTableManager([MockDataSourceProvider({
            ds_1_domain: [data_source_1]
        })])
        table_manager.bootstrap()
        # test in same domain
        data_source_2 = self._copy_data_source(data_source_1)
        data_source_2.save()
        table_manager._add_data_sources_to_table_adapters([data_source_2], set())
        self.assertEqual(1, len(table_manager.table_adapters_by_domain))
        self.assertEqual(2, len(table_manager.table_adapters_by_domain[ds_1_domain]))
        self.assertEqual(
            {data_source_1, data_source_2},
            set([table_adapter.config for table_adapter in table_manager.table_adapters_by_domain[ds_1_domain]])
        )
        # test in a new domain
        data_source_3 = self._copy_data_source(data_source_1)
        ds3_domain = 'new_domain'
        data_source_3.domain = ds3_domain
        data_source_3.save()
        table_manager._add_data_sources_to_table_adapters([data_source_3], set())
        # should now be 2 domains in the map
        self.assertEqual(2, len(table_manager.table_adapters_by_domain))
        # ensure domain 1 unchanged
        self.assertEqual(
            {data_source_1, data_source_2},
            set([table_adapter.config for table_adapter in table_manager.table_adapters_by_domain[ds_1_domain]])
        )
        self.assertEqual(1, len(table_manager.table_adapters_by_domain[ds3_domain]))
        self.assertEqual(data_source_3, table_manager.table_adapters_by_domain[ds3_domain][0].config)

        # finally pass in existing data sources and ensure they modify in place
        table_manager._add_data_sources_to_table_adapters([data_source_1, data_source_3], set())
        self.assertEqual(2, len(table_manager.table_adapters_by_domain))
        self.assertEqual(
            {data_source_1, data_source_2},
            set([table_adapter.config for table_adapter in table_manager.table_adapters_by_domain[ds_1_domain]])
        )
        self.assertEqual(data_source_3, table_manager.table_adapters_by_domain[ds3_domain][0].config)

    def test_complete_integration(self):
        # initialize pillow with one data source
        data_source_1 = get_sample_data_source()
        data_source_1.save()
        ds_1_domain = data_source_1.domain
        table_manager = ConfigurableReportTableManager([DynamicDataSourceProvider()])
        table_manager.bootstrap()
        self.assertEqual(1, len(table_manager.table_adapters_by_domain))
        self.assertEqual(1, len(table_manager.table_adapters_by_domain[ds_1_domain]))
        self.assertEqual(data_source_1._id, table_manager.table_adapters_by_domain[ds_1_domain][0].config._id)

        data_source_2 = self._copy_data_source(data_source_1)
        data_source_2.save()
        self.assertFalse(table_manager.needs_bootstrap())
        # should call _update_modified_data_sources
        table_manager.bootstrap_if_needed()
        self.assertEqual(1, len(table_manager.table_adapters_by_domain))
        self.assertEqual(2, len(table_manager.table_adapters_by_domain[ds_1_domain]))
        self.assertEqual(
            {data_source_1._id, data_source_2._id},
            {t.config._id for t in table_manager.table_adapters_by_domain[ds_1_domain]}
        )

    @patch("corehq.apps.cachehq.mixins.invalidate_document")
    def test_bad_spec_error(self, _):
        ExpressionFactory.register("missing_expression", lambda x, y: x)
        data_source_1 = get_sample_data_source()
        data_source_1.configured_indicators[0] = {
            "column_id": "date",
            "type": "expression",
            "expression": {
                "type": "missing_expression",
            },
            "datatype": "datetime"
        }
        data_source_1.save()
        del ExpressionFactory.spec_map["missing_expression"]
        ds_1_domain = data_source_1.domain
        table_manager = ConfigurableReportTableManager([DynamicDataSourceProvider()])
        table_manager.bootstrap()
        self.assertEqual(0, len(table_manager.table_adapters_by_domain))
        self.assertEqual(0, len(table_manager.table_adapters_by_domain[ds_1_domain]))

    def _copy_data_source(self, data_source):
        data_source_json = data_source.to_json()
        if data_source_json.get('_id'):
            del data_source_json['_id']
        return DataSourceConfiguration.wrap(data_source_json)


class ChunkedUCRProcessorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ChunkedUCRProcessorTest, cls).setUpClass()
        cls.config = get_sample_data_source()
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        cls.pillow = _get_pillow([cls.config], processor_chunk_size=100)

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super(ChunkedUCRProcessorTest, cls).tearDownClass()

    def tearDown(self):
        self.adapter.clear_table()
        delete_all_cases()
        delete_all_xforms()
        InvalidUCRData.objects.all().delete()
        self.config = DataSourceConfiguration.get(self.config.data_source_id)
        self.config.validations = []
        self.config.save()

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    def test_basic_sql(self, processor_patch):
        cases = self._create_and_process_changes()
        rows = self.adapter.get_query_object().all()
        self.assertEqual(
            set([case.case_id for case in cases]),
            set([row.doc_id for row in rows])
        )
        # processor.process_change should not get called but processor.process_changes_chunk
        self.assertFalse(processor_patch.called)

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def _create_cases(self, datetime_mock, docs=[]):
        datetime_mock.utcnow.return_value = self.fake_time_now
        docs = docs or [
            get_sample_doc_and_indicators(self.fake_time_now)[0]
            for i in range(10)
        ]

        # save case to DB - should also publish to kafka
        cases = [
            _save_sql_case(doc)
            for doc in docs
        ]
        return cases

    def _create_and_process_changes(self, docs=[]):
        self.pillow = _get_pillow([self.config], processor_chunk_size=100)
        since = self.pillow.get_change_feed().get_latest_offsets()
        cases = self._create_cases(docs=docs)
        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        return cases

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_changes_chunk')
    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    def test_full_fallback(self, process_change_patch, process_changes_patch):

        process_changes_patch.side_effect = Exception
        self._create_and_process_changes()

        process_changes_patch.assert_called_once()
        # since chunked processing failed, normal processing should get called
        process_change_patch.assert_has_calls([mock.call(mock.ANY)] * 10)

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    @mock.patch('corehq.form_processor.document_stores.CaseDocumentStore.iter_documents')
    def test_partial_fallback_calls(self, iter_docs_patch, process_change_patch):
        # this is equivalent to failing on last 4 docs, since they are missing in docstore
        docs = [
            get_sample_doc_and_indicators(self.fake_time_now)[0]
            for i in range(10)
        ]
        iter_docs_patch.return_value = docs[0:6]
        self._create_and_process_changes(docs)

        # since chunked processing failed, normal processing should get called
        process_change_patch.assert_has_calls([mock.call(mock.ANY)] * 4)

    @mock.patch('corehq.form_processor.document_stores.CaseDocumentStore.iter_documents')
    def test_partial_fallback_data(self, iter_docs_patch):
        docs = [
            get_sample_doc_and_indicators(self.fake_time_now)[0]
            for i in range(10)
        ]
        # this is equivalent to failing on last 5 docs, since they are missing in docstore
        iter_docs_patch.return_value = docs[0:5]
        cases = self._create_and_process_changes(docs=docs)
        query = self.adapter.get_query_object()
        # first five docs should be processed in bulk, last five serially
        self.assertEqual(query.count(), 10)
        self.assertEqual(
            set([case.case_id for case in cases]),
            set([row.doc_id for row in query.all()])
        )

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    def test_invalid_data_bulk_processor(self, process_change):
        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)

        self.config.validations = [
            Validation.wrap({
                "name": "impossible_condition",
                "error_message": "This condition is impossible to satisfy",
                "expression": {
                    "type": "boolean_expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "doesnt_exist"
                    },
                    "operator": "in",
                    "property_value": ["nonsense"]
                }
            })
        ]
        self.config.save()

        cases = self._create_and_process_changes()
        num_rows = self.adapter.get_query_object().count()
        self.assertEqual(num_rows, 0)
        invalid_data = InvalidUCRData.objects.all().values_list('doc_id', flat=True)
        self.assertEqual(set([case.case_id for case in cases]), set(invalid_data))
        # processor.process_change should not get called but processor.process_changes_chunk
        self.assertFalse(process_change.called)

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_changes_chunk')
    def test_invalid_data_serial_processor(self, process_changes_chunk):
        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)

        process_changes_chunk.side_effect = Exception
        self.config.validations = [
            Validation.wrap({
                "name": "impossible_condition",
                "error_message": "This condition is impossible to satisfy",
                "expression": {
                    "type": "boolean_expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "doesnt_exist"
                    },
                    "operator": "in",
                    "property_value": ["nonsense"]
                }
            })
        ]
        self.config.save()

        cases = self._create_and_process_changes()
        num_rows = self.adapter.get_query_object().count()
        self.assertEqual(num_rows, 0)
        invalid_data = InvalidUCRData.objects.all().values_list('doc_id', flat=True)
        self.assertEqual(set([case.case_id for case in cases]), set(invalid_data))

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportTableManager.bootstrap_if_needed')
    def test_bootstrap_if_needed(self, bootstrap_if_needed):
        self._create_and_process_changes()
        bootstrap_if_needed.assert_called_once_with()


class IndicatorPillowTest(BaseRepeaterTest):

    domain = "user-reports"

    @classmethod
    def setUpClass(cls):
        super(IndicatorPillowTest, cls).setUpClass()
        cls.config = get_sample_data_source()
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        cls.pillow = _get_pillow([cls.config])
        cls.conn_setting = ConnectionSettings.objects.create(
            domain=cls.domain,
            name="TestConnectionSetting",
            url="http://example.test",
        )

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super(IndicatorPillowTest, cls).tearDownClass()

    def tearDown(self):
        delete_all_repeat_records()
        self.adapter.clear_table()

    @flaky_slow
    @mock.patch('corehq.apps.userreports.specs.datetime')
    def _check_sample_doc_state(self, expected_indicators, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        self.assertEqual(1, self.adapter.get_query_object().count())
        row = self.adapter.get_query_object()[0]
        for k in row.keys():
            v = getattr(row, k)
            if isinstance(expected_indicators[k], decimal.Decimal):
                self.assertAlmostEqual(expected_indicators[k], v)
            else:
                self.assertEqual(
                    expected_indicators[k], v,
                    'mismatched property: {} (expected {}, was {})'.format(
                        k, expected_indicators[k], v
                    )
                )

    def test_stale_rebuild(self):
        # rebuild indicators in another test will save this
        later_config = DataSourceConfiguration.get(self.config._id)
        later_config.save()
        self.assertNotEqual(self.config._rev, later_config._rev)
        with self.assertRaises(StaleRebuildError):
            rebuild_table(get_indicator_adapter(self.config))

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_change_transport(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @flag_enabled('SUPERSET_ANALYTICS')
    @mock.patch('corehq.motech.repeaters.signals.create_repeat_records')
    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_datasource_change_triggers_change_signal(self, datetime_mock, create_repeat_records_mock):
        from corehq.apps.userreports.util import DataSourceUpdateLog
        data_source_id = self.config._id
        num_repeaters = 2
        self._setup_data_source_subscription(self.config.domain, data_source_id, num_repeaters=num_repeaters)

        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, _expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))

        # Assert that a repeat records will be created, since there is a DataSourceRepeater for this datasource
        create_repeat_records_mock.assert_called()
        # Assert that it will be created with the expected args
        call_args = create_repeat_records_mock.call_args[0]
        self.assertEqual(call_args[0], DataSourceRepeater)
        self.assertTrue(isinstance(call_args[1], DataSourceUpdateLog))
        update_log = call_args[1]
        self.assertEqual(update_log.domain, self.domain)
        self.assertEqual(update_log.data_source_id, self.config._id)
        self.assertEqual(update_log.doc_id, sample_doc["_id"])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_rebuild_indicators(self, datetime_mock):
        data_source_id = self.config._id
        self._setup_data_source_subscription(self.config.domain, data_source_id)
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        _save_sql_case(sample_doc)
        rebuild_indicators(data_source_id)
        self._check_sample_doc_state(expected_indicators)

    def test_bad_integer_datatype(self):
        bad_ints = ['a', '', None]
        for bad_value in bad_ints:
            self.pillow.process_change(doc_to_change({
                '_id': uuid.uuid4().hex,
                'doc_type': 'CommCareCase',
                'domain': 'user-reports',
                'type': 'ticket',
                'priority': bad_value
            }))
        # make sure we saved rows to the table for everything
        self.assertEqual(len(bad_ints), self.adapter.get_query_object().count())

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_basic_doc_processing(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_not_relevant_to_domain(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        sample_doc['domain'] = 'not-this-domain'
        self.pillow.process_change(doc_to_change(sample_doc))
        self.assertEqual(0, self.adapter.get_query_object().count())

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_sql_chunked(self, datetime_mock):
        self.pillow = _get_pillow([self.config], processor_chunk_size=100)
        self._test_process_doc_from_sql(datetime_mock)
        self.pillow = _get_pillow([self.config])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_sql(self, datetime_mock):
        self._test_process_doc_from_sql(datetime_mock)

    def _test_process_doc_from_sql(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        since = self.pillow.get_change_feed().get_latest_offsets()

        # save case to DB - should also publish to kafka
        case = _save_sql_case(sample_doc)

        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)

        CommCareCase.objects.hard_delete_cases(case.domain, [case.case_id])

    @flag_enabled('SUPERSET_ANALYTICS')
    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_deleted_doc_from_sql_chunked(self, datetime_mock):
        self._setup_data_source_subscription(self.config.domain, self.config._id, num_repeaters=2)

        self.pillow = _get_pillow([self.config], processor_chunk_size=100)
        self._test_process_deleted_doc_from_sql(datetime_mock)
        self.pillow = _get_pillow([self.config])
        later = datetime.utcnow() + timedelta(hours=50)
        repeat_records = SQLRepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)
        # We expect 2 repeat records for 2 repeaters each
        self.assertEqual(repeat_records.count(), 4)

    @flag_enabled('SUPERSET_ANALYTICS')
    @mock.patch('corehq.motech.repeaters.models.Repeater.register')
    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_delete_doc_should_not_forward_change(self, datetime_mock, register_mock):
        """Test that a no attempt is made to register a repeat record if there's no data source repeater"""
        self._test_process_deleted_doc_from_sql(datetime_mock)
        self.assertEqual(register_mock.call_count, 0)

    def _setup_data_source_subscription(self, domain, data_source_id, num_repeaters=1):
        for _i in range(num_repeaters):
            DataSourceRepeater.objects.create(
                data_source_id=data_source_id,
                domain=domain,
                connection_settings_id=self.conn_setting.id,
            )
        self.assertTrue(DataSourceRepeater.datasource_is_subscribed_to(domain, data_source_id))

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_deleted_doc_from_sql(self, datetime_mock):
        self._test_process_deleted_doc_from_sql(datetime_mock)

    def _test_process_deleted_doc_from_sql(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        since = self.pillow.get_change_feed().get_latest_offsets()

        # save case to DB - should also publish to kafka
        case = _save_sql_case(sample_doc)

        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)

        # delete the case and verify it's removed
        since = self.pillow.get_change_feed().get_latest_offsets()
        CommCareCase.objects.soft_delete_cases(case.domain, [case.case_id])
        self.pillow.process_changes(since=since, forever=False)
        self.assertEqual(0, self.adapter.get_query_object().count())

        CommCareCase.objects.hard_delete_cases(case.domain, [case.case_id])
        return sample_doc

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_filter_no_longer_pass(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

        sample_doc['doc_type'] = 'CommCareCase-Deleted'

        self.pillow.process_change(doc_to_change(sample_doc))

        self.assertEqual(0, self.adapter.get_query_object().count())

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_check_if_doc_exist(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.assertFalse(self.adapter.doc_exists(sample_doc))

        self.pillow.process_change(doc_to_change(sample_doc))

        self.assertIs(self.adapter.doc_exists(sample_doc), True)


class ProcessRelatedDocTypePillowTest(TestCase):
    domain = 'bug-domain'

    @softer_assert()
    def setUp(self):
        self.config = get_data_source_with_related_doc_type()
        self.config.save()
        self.adapter = get_indicator_adapter(self.config)
        self.pillow = _get_pillow([self.config])
        self.pillow.get_change_feed().get_latest_offsets()

    def tearDown(self):
        self.config = DataSourceConfiguration.get(self.config.data_source_id)
        self.config.delete()
        self.adapter.drop_table()
        delete_all_cases()
        delete_all_xforms()

    def _post_case_blocks(self, iteration=0):
        return submit_case_blocks(
            [
                CaseBlock(
                    create=iteration == 0,
                    case_id='parent-id',
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': iteration},
                ).as_text(),
                CaseBlock(
                    create=iteration == 0,
                    case_id='child-id',
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', 'parent-id')},
                    update={'update-prop-child': iteration}
                ).as_text()
            ], domain=self.domain
        )

    def test_process_doc_from_sql_stale_chunked(self):
        pillow = _get_pillow([self.config], processor_chunk_size=100)
        # expected queries:  1 less since parent + child fetched together
        # get cases (parent + child)
        # get case indices (child)
        # get case (parent)
        self._test_process_doc_from_sql_stale(pillow, num_queries=3)

    def test_process_doc_from_sql_stale(self):
        # expected queries:
        # get case (parent)
        # get case (child)
        # get case indices (child)
        # get case (parent)
        self._test_process_doc_from_sql_stale()

    def _test_process_doc_from_sql_stale(self, pillow=None, num_queries=4):
        '''
        Ensures that when you update a case that the changes are reflected in
        the UCR table.

        http://manage.dimagi.com/default.asp?245341
        '''
        with mock.patch(
                'corehq.pillows.case.KafkaCheckpointEventHandler.should_update_checkpoint',
                return_value=False
        ):
            pillow = pillow or self.pillow
            for i in range(3):
                since = pillow.get_change_feed().get_latest_offsets()
                form, cases = self._post_case_blocks(i)
                with self.assertNumQueries(num_queries):
                    pillow.process_changes(since=since, forever=False)
                rows = self.adapter.get_query_object()
                self.assertEqual(rows.count(), 1)
                row = rows[0]
                self.assertEqual(int(row.parent_property), i)
                errors = PillowError.objects.filter(doc_id='child-id', pillow=pillow.pillow_id)
                self.assertEqual(errors.count(), 0)


class ReuseEvaluationContextTest(TestCase):
    domain = 'bug-domain'

    @softer_assert()
    def setUp(self):
        config1 = get_data_source_with_related_doc_type()
        config1.save()
        config2 = get_data_source_with_related_doc_type()
        config2.table_id = 'other-config'
        config2.save()
        self.configs = [config1, config2]
        self.adapters = [get_indicator_adapter(c) for c in self.configs]

        # one pillow that has one config, the other has both configs
        self.pillow1 = _get_pillow([config1])
        self.pillow2 = _get_pillow(self.configs)

        self.pillow1.get_change_feed().get_latest_offsets()

    def tearDown(self):
        for adapter in self.adapters:
            adapter.drop_table()
            adapter.config.delete()
        delete_all_cases()
        delete_all_xforms()

    def _post_case_blocks(self, iteration=0):
        return submit_case_blocks(
            [
                CaseBlock(
                    create=iteration == 0,
                    case_id='parent-id',
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': iteration},
                ).as_text(),
                CaseBlock(
                    create=iteration == 0,
                    case_id='child-id',
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', 'parent-id')},
                    update={'update-prop-child': iteration}
                ).as_text()
            ], domain=self.domain
        )

    def _test_pillow(self, pillow, since, num_queries=12):
        with mock.patch(
                'corehq.pillows.case.KafkaCheckpointEventHandler.should_update_checkpoint',
                return_value=False
        ):
            with self.assertNumQueries(num_queries):
                pillow.process_changes(since=since, forever=False)

    def test_reuse_cache(self):
        self._test_reuse_cache()

    def test_reuse_cache_chunked(self):
        pillow1 = _get_pillow(self.configs[:1], processor_chunk_size=100)
        pillow2 = _get_pillow(self.configs, processor_chunk_size=100)
        self._test_reuse_cache(pillow1, pillow2, 3)

    def _test_reuse_cache(self, pillow1=None, pillow2=None, num_queries=4):
        # tests that these two pillows make the same number of DB calls even
        # though pillow2 has an extra config
        pillow1 = pillow1 or self.pillow1
        pillow2 = pillow2 or self.pillow2
        since1 = pillow1.get_change_feed().get_latest_offsets()
        since2 = pillow2.get_change_feed().get_latest_offsets()
        form, cases = self._post_case_blocks()

        self._test_pillow(pillow1, since1, num_queries)
        self._test_pillow(pillow2, since2, num_queries)

        for a in self.adapters:
            rows = a.get_query_object()
            self.assertEqual(rows.count(), 1)
            self.assertEqual(int(rows[0].parent_property), 0)


class AsyncIndicatorTest(TestCase):
    domain = 'bug-domain'

    @classmethod
    @softer_assert()
    def setUpClass(cls):
        super(AsyncIndicatorTest, cls).setUpClass()
        cls.config = get_data_source_with_related_doc_type()
        cls.config.asynchronous = True
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.pillow = _get_pillow([cls.config])
        cls.pillow.get_change_feed().get_latest_offsets()

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super(AsyncIndicatorTest, cls).tearDownClass()

    def tearDown(self):
        delete_all_cases()
        delete_all_xforms()
        AsyncIndicator.objects.all().delete()
        InvalidUCRData.objects.all().delete()
        self.config = DataSourceConfiguration.get(self.config.data_source_id)
        self.config.validations = []
        self.config.save()

    @flaky_slow
    def test_async_save_success(self):
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        for i in range(3):
            since = self.pillow.get_change_feed().get_latest_offsets()
            submit_case_blocks(
                [
                    CaseBlock(
                        create=i == 0,
                        case_id=parent_id,
                        case_name='parent-name',
                        case_type='bug',
                        update={'update-prop-parent': i},
                    ).as_text(),
                    CaseBlock(
                        create=i == 0,
                        case_id=child_id,
                        case_name='child-name',
                        case_type='bug-child',
                        index={'parent': ('bug', parent_id)},
                        update={'update-prop-child': i}
                    ).as_text()
                ], domain=self.domain
            )
            # ensure indicator is added
            indicators = AsyncIndicator.objects.filter(doc_id=child_id)
            self.assertEqual(indicators.count(), 0)
            self.pillow.process_changes(since=since, forever=False)
            self.assertEqual(indicators.count(), 1)

            # ensure saving document produces a row
            queue_async_indicators()
            rows = self.adapter.get_query_object()
            self.assertEqual(rows.count(), 1)

            # ensure row is correct
            row = rows[0]
            self.assertEqual(int(row.parent_property), i)

            # ensure no errors or anything left in the queue
            errors = PillowError.objects.filter(doc_id=child_id, pillow=self.pillow.pillow_id)
            self.assertEqual(errors.count(), 0)
            self.assertEqual(indicators.count(), 0)

    @mock.patch('corehq.apps.userreports.tasks.get_ucr_datasource_config_by_id')
    def test_async_save_fails(self, config):
        # process_changes will generate an exception when trying to use this config
        config.return_value = None
        since = self.pillow.get_change_feed().get_latest_offsets()
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        submit_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=parent_id,
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': 0},
                ).as_text(),
                CaseBlock(
                    create=True,
                    case_id=child_id,
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', parent_id)},
                    update={'update-prop-child': 0}
                ).as_text()
            ], domain=self.domain
        )

        # ensure async indicator is added
        indicators = AsyncIndicator.objects.filter(doc_id=child_id)
        self.assertEqual(indicators.count(), 0)
        self.pillow.process_changes(since=since, forever=False)
        self.assertEqual(indicators.count(), 1)

        queue_async_indicators()

        rows = self.adapter.get_query_object()
        self.assertEqual(rows.count(), 0)

        # ensure there is not a pillow error and the async indicator is still there
        errors = PillowError.objects.filter(doc_id=child_id, pillow=self.pillow.pillow_id)
        self.assertEqual(errors.count(), 0)
        self.assertEqual(indicators.count(), 1)

    @flaky_slow
    def test_async_invalid_data(self):
        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)

        self.config.validations = [
            Validation.wrap({
                "name": "impossible_condition",
                "error_message": "This condition is impossible to satisfy",
                "expression": {
                    "type": "boolean_expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "doesnt_exist"
                    },
                    "operator": "in",
                    "property_value": ["nonsense"]
                }
            })
        ]

        self.config.save()
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        since = self.pillow.get_change_feed().get_latest_offsets()
        for i in range(3):
            submit_case_blocks(
                [
                    CaseBlock(
                        create=i == 0,
                        case_id=parent_id,
                        case_name='parent-name',
                        case_type='bug',
                        update={'update-prop-parent': i},
                    ).as_text(),
                    CaseBlock(
                        create=i == 0,
                        case_id=child_id,
                        case_name='child-name',
                        case_type='bug-child',
                        index={'parent': ('bug', parent_id)},
                        update={'update-prop-child': i}
                    ).as_text()
                ], domain=self.domain
            )
        self.pillow.process_changes(since=since, forever=False)

        # run async queue
        queue_async_indicators()
        self.assertEqual(InvalidUCRData.objects.count(), 1)


class ChunkedAsyncIndicatorTest(AsyncIndicatorTest):

    @classmethod
    def setUpClass(cls):
        super(ChunkedAsyncIndicatorTest, cls).setUpClass()
        cls.pillow = _get_pillow([cls.config], processor_chunk_size=100)


class IndicatorConfigFilterTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_data_source()

    def test_filter(self):
        not_matching = [
            dict(doc_type="NotCommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='not-user-reports', type='ticket'),
            dict(doc_type="CommCareCase", domain='user-reports', type='not-ticket'),
        ]
        for document in not_matching:
            self.assertFalse(self.config.filter(document)), 'Failing dog: %s' % document

        self.assertTrue(self.config.filter(
            dict(doc_type="CommCareCase", domain='user-reports', type='ticket')
        ))

    def test_deleted_filter(self):
        not_matching = [
            dict(doc_type="CommCareCase", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase-Deleted", domain='not-user-reports', type='ticket'),
        ]
        for document in not_matching:
            self.assertFalse(self.config.deleted_filter(document), 'Failing dog: %s' % document)

        matching = [
            dict(doc_type="CommCareCase-Deleted", domain='user-reports', type='ticket'),
            dict(doc_type="CommCareCase-Deleted", domain='user-reports', type='bot-ticket'),
            dict(doc_type="CommCareCase-Deleted", domain='user-reports'),
        ]
        for document in matching:
            self.assertTrue(self.config.deleted_filter(document), 'Failing dog: %s' % document)


def _save_sql_case(doc):
    system_props = ['_id', '_rev', 'opened_on', 'owner_id', 'doc_type', 'domain', 'type']
    with drop_connected_signals(sql_case_post_save):
        form, cases = submit_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=doc['_id'],
                    case_name=doc['name'],
                    case_type=doc['type'],
                    owner_id=doc['owner_id'],
                    date_opened=doc['opened_on'],
                    update={k: str(v) for k, v in doc.items() if k not in system_props}
                ).as_text()
            ], domain=doc['domain']
        )
    return cases[0]
