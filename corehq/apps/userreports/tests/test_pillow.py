from __future__ import absolute_import
from __future__ import unicode_literals

import decimal
import uuid
from datetime import datetime, timedelta

import mock
from django.test import TestCase, SimpleTestCase, override_settings
from six.moves import range

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import post_case_blocks
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.userreports.data_source_providers import MockDataSourceProvider
from corehq.apps.userreports.exceptions import StaleRebuildError
from corehq.apps.userreports.models import DataSourceConfiguration, AsyncIndicator, Validation, InvalidUCRData
from corehq.apps.userreports.pillow import REBUILD_CHECK_INTERVAL, \
    ConfigurableReportTableManagerMixin, \
    ConfigurableReportPillowProcessor
from corehq.apps.userreports.tasks import rebuild_indicators, queue_async_indicators
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators, \
    doc_to_change, get_data_source_with_related_doc_type, skip_domain_filter_patch
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.pillows.case import get_case_pillow
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import softer_assert
from pillow_retry.models import PillowError


def setup_module():
    skip_domain_filter_patch.start()


def teardown_module():
    skip_domain_filter_patch.stop()


def _get_pillow(configs, processor_chunk_size=0):
    pillow = get_case_pillow(processor_chunk_size=processor_chunk_size)
    # overwrite processors since we're only concerned with UCR here
    ucr_processor = ConfigurableReportPillowProcessor(data_source_providers=[])
    ucr_processor.bootstrap(configs)
    pillow.processors = [ucr_processor]
    return pillow


class ConfigurableReportTableManagerTest(SimpleTestCase):

    def test_needs_bootstrap_on_initialization(self):
        table_manager = ConfigurableReportTableManagerMixin([MockDataSourceProvider()])
        self.assertTrue(table_manager.needs_bootstrap())

    def test_bootstrap_sets_time(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin([MockDataSourceProvider()])
        table_manager.bootstrap([])
        after_now = datetime.utcnow() + timedelta(microseconds=1)
        self.assertTrue(table_manager.bootstrapped)
        self.assertTrue(before_now < table_manager.last_bootstrapped)
        self.assertTrue(after_now > table_manager.last_bootstrapped)
        self.assertFalse(table_manager.needs_bootstrap())

    def test_needs_bootstrap_window(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin([MockDataSourceProvider()])
        table_manager.bootstrap([])
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL - 5)
        self.assertFalse(table_manager.needs_bootstrap())
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL)
        self.assertTrue(table_manager.needs_bootstrap())


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
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
        since = self.pillow.get_change_feed().get_latest_offsets()
        cases = self._create_cases(docs=docs)
        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        return cases

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_changes_chunk')
    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    def test_full_fallback(self, process_change_patch, process_changes_patch):

        process_changes_patch.side_effect = Exception
        cases = self._create_and_process_changes()

        process_changes_patch.assert_called_once()
        # since chunked processing failed, normal processing should get called
        process_change_patch.assert_has_calls([mock.call(mock.ANY)] * 10)

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    @mock.patch('corehq.form_processor.document_stores.ReadonlyCaseDocumentStore.iter_documents')
    def test_partial_fallback_calls(self, iter_docs_patch, process_change_patch):
        # this is equivalent to failing on last 4 docs, since they are missing in docstore
        docs = [
            get_sample_doc_and_indicators(self.fake_time_now)[0]
            for i in range(10)
        ]
        iter_docs_patch.return_value = docs[0:6]
        cases = self._create_and_process_changes(docs)

        # since chunked processing failed, normal processing should get called
        process_change_patch.assert_has_calls([mock.call(mock.ANY)] * 4)

    @mock.patch('corehq.form_processor.document_stores.ReadonlyCaseDocumentStore.iter_documents')
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

    def test_get_docs(self):
        docs = [
            get_sample_doc_and_indicators(self.fake_time_now)[0]
            for i in range(10)
        ]
        feed = self.pillow.get_change_feed()
        since = feed.get_latest_offsets()
        cases = self._create_cases(docs=docs)
        changes = list(feed.iter_changes(since, forever=False))
        bad_changes, result_docs = ConfigurableReportPillowProcessor.get_docs_for_changes(
            changes, docs[1]['domain'])
        self.assertEqual(
            set([c.id for c in changes]),
            set([doc['_id'] for doc in result_docs])
        )

    @mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.process_change')
    def test_invalid_data_bulk_processor(self, process_change):
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


class IndicatorPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IndicatorPillowTest, cls).setUpClass()
        cls.config = get_sample_data_source()
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        cls.pillow = _get_pillow([cls.config])

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super(IndicatorPillowTest, cls).tearDownClass()

    def tearDown(self):
        self.adapter.clear_table()

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
            self.pillow.processors[0].rebuild_table(get_indicator_adapter(self.config))

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_change_transport(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_rebuild_indicators(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        CommCareCase.get_db().save_doc(sample_doc)
        self.addCleanup(lambda id: CommCareCase.get_db().delete_doc(id), sample_doc['_id'])
        rebuild_indicators(self.config._id)
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
    def test_process_doc_from_couch_chunked(self, datetime_mock):
        pillow = _get_pillow([self.config], processor_chunk_size=100)
        self._test_process_doc_from_couch(datetime_mock, pillow)

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_couch(self, datetime_mock):
        self._test_process_doc_from_couch(datetime_mock, self.pillow)

    def _test_process_doc_from_couch(self, datetime_mock, pillow):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        # make sure case is in DB
        case = CommCareCase.wrap(sample_doc)
        with drop_connected_signals(case_post_save):
            case.save()

        # send to kafka
        since = self.pillow.get_change_feed().get_latest_offsets()
        producer.send_change(topics.CASE, doc_to_change(sample_doc).metadata)

        # run pillow and check changes
        pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)
        case.delete()

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_sql_chunked(self, datetime_mock):
        self.pillow = _get_pillow([self.config], processor_chunk_size=100)
        self._test_process_doc_from_sql(datetime_mock)
        self.pillow = _get_pillow([self.config])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_sql(self, datetime_mock):
        self._test_process_doc_from_sql(datetime_mock)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def _test_process_doc_from_sql(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        since = self.pillow.get_change_feed().get_latest_offsets()

        # save case to DB - should also publish to kafka
        case = _save_sql_case(sample_doc)

        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)

        CaseAccessorSQL.hard_delete_cases(case.domain, [case.case_id])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_deleted_doc_from_sql_chunked(self, datetime_mock):
        self.pillow = _get_pillow([self.config], processor_chunk_size=100)
        self._test_process_deleted_doc_from_sql(datetime_mock)
        self.pillow = _get_pillow([self.config])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    def test_process_deleted_doc_from_sql(self, datetime_mock):
        self._test_process_deleted_doc_from_sql(datetime_mock)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
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
        CaseAccessorSQL.soft_delete_cases(case.domain, [case.case_id])
        self.pillow.process_changes(since=since, forever=False)
        self.assertEqual(0, self.adapter.get_query_object().count())

        CaseAccessorSQL.hard_delete_cases(case.domain, [case.case_id])

    @mock.patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_process_filter_no_longer_pass(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

        sample_doc['type'] = 'wrong_type'

        self.pillow.process_change(doc_to_change(sample_doc))

        self.assertEqual(0, self.adapter.get_query_object().count())

    @mock.patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_check_if_doc_exist(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.assertFalse(self.adapter.doc_exists(sample_doc))

        self.pillow.process_change(doc_to_change(sample_doc))

        self.assertIs(self.adapter.doc_exists(sample_doc), True)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
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
        self.config.delete()
        self.adapter.drop_table()
        delete_all_cases()
        delete_all_xforms()

    def _post_case_blocks(self, iteration=0):
        return post_case_blocks(
            [
                CaseBlock(
                    create=iteration == 0,
                    case_id='parent-id',
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': iteration},
                ).as_xml(),
                CaseBlock(
                    create=iteration == 0,
                    case_id='child-id',
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', 'parent-id')},
                    update={'update-prop-child': iteration}
                ).as_xml()
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
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
        return post_case_blocks(
            [
                CaseBlock(
                    create=iteration == 0,
                    case_id='parent-id',
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': iteration},
                ).as_xml(),
                CaseBlock(
                    create=iteration == 0,
                    case_id='child-id',
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', 'parent-id')},
                    update={'update-prop-child': iteration}
                ).as_xml()
            ], domain=self.domain
        )

    def _test_pillow(self, pillow, since, num_queries=12):
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
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
        self.config.validations = []
        self.config.save()

    def test_async_save_success(self):
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        for i in range(3):
            since = self.pillow.get_change_feed().get_latest_offsets()
            form, cases = post_case_blocks(
                [
                    CaseBlock(
                        create=i == 0,
                        case_id=parent_id,
                        case_name='parent-name',
                        case_type='bug',
                        update={'update-prop-parent': i},
                    ).as_xml(),
                    CaseBlock(
                        create=i == 0,
                        case_id=child_id,
                        case_name='child-name',
                        case_type='bug-child',
                        index={'parent': ('bug', parent_id)},
                        update={'update-prop-child': i}
                    ).as_xml()
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

    @mock.patch('corehq.apps.userreports.tasks._get_config_by_id')
    def test_async_save_fails(self, config):
        # process_changes will generate an exception when trying to use this config
        config.return_value = None
        since = self.pillow.get_change_feed().get_latest_offsets()
        parent_id, child_id = uuid.uuid4().hex, uuid.uuid4().hex
        form, cases = post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=parent_id,
                    case_name='parent-name',
                    case_type='bug',
                    update={'update-prop-parent': 0},
                ).as_xml(),
                CaseBlock(
                    create=True,
                    case_id=child_id,
                    case_name='child-name',
                    case_type='bug-child',
                    index={'parent': ('bug', parent_id)},
                    update={'update-prop-child': 0}
                ).as_xml()
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

    def test_async_invalid_data(self):
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
            form, cases = post_case_blocks(
                [
                    CaseBlock(
                        create=i == 0,
                        case_id=parent_id,
                        case_name='parent-name',
                        case_type='bug',
                        update={'update-prop-parent': i},
                    ).as_xml(),
                    CaseBlock(
                        create=i == 0,
                        case_id=child_id,
                        case_name='child-name',
                        case_type='bug-child',
                        index={'parent': ('bug', parent_id)},
                        update={'update-prop-child': i}
                    ).as_xml()
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
    with drop_connected_signals(case_post_save):
        form, cases = post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=doc['_id'],
                    case_name=doc['name'],
                    case_type=doc['type'],
                    owner_id=doc['owner_id'],
                    date_opened=doc['opened_on'],
                    update={k: str(v) for k, v in doc.items() if k not in system_props}
                ).as_xml()
            ], domain=doc['domain']
        )
    return cases[0]
