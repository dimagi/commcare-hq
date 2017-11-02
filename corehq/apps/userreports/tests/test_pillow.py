from __future__ import absolute_import
import decimal
import uuid
from django.test import TestCase, SimpleTestCase, override_settings
from kafka.common import KafkaUnavailableError
from mock import patch, MagicMock
from datetime import datetime, timedelta
from six.moves import range
from sqlalchemy.engine import reflection

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import post_case_blocks

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.userreports.const import UCR_SQL_BACKEND, UCR_ES_BACKEND
from corehq.apps.userreports.data_source_providers import MockDataSourceProvider
from corehq.apps.userreports.exceptions import StaleRebuildError
from corehq.apps.userreports.models import DataSourceConfiguration, AsyncIndicator
from corehq.apps.userreports.pillow import REBUILD_CHECK_INTERVAL, \
    ConfigurableReportTableManagerMixin, get_kafka_ucr_pillow, get_kafka_ucr_static_pillow
from corehq.apps.userreports.tasks import rebuild_indicators, queue_async_indicators
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators, \
    doc_to_change, get_data_source_with_related_doc_type
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.util.test_utils import softer_assert, trap_extra_setup
from corehq.util.context_managers import drop_connected_signals
from pillow_retry.models import PillowError


class ConfigurableReportTableManagerTest(SimpleTestCase):

    def test_needs_bootstrap_on_initialization(self):
        table_manager = ConfigurableReportTableManagerMixin(MockDataSourceProvider())
        self.assertTrue(table_manager.needs_bootstrap())

    def test_bootstrap_sets_time(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin(MockDataSourceProvider())
        table_manager.bootstrap([])
        after_now = datetime.utcnow() + timedelta(microseconds=1)
        self.assertTrue(table_manager.bootstrapped)
        self.assertTrue(before_now < table_manager.last_bootstrapped)
        self.assertTrue(after_now > table_manager.last_bootstrapped)
        self.assertFalse(table_manager.needs_bootstrap())

    def test_needs_bootstrap_window(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin(MockDataSourceProvider())
        table_manager.bootstrap([])
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL - 5)
        self.assertFalse(table_manager.needs_bootstrap())
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL)
        self.assertTrue(table_manager.needs_bootstrap())


@override_settings(OVERRIDE_UCR_BACKEND=UCR_SQL_BACKEND)
class IndicatorPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(IndicatorPillowTest, cls).setUpClass()
        cls.config = get_sample_data_source()
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)
        cls.adapter.build_table()
        cls.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        cls.pillow = get_kafka_ucr_pillow()

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        super(IndicatorPillowTest, cls).tearDownClass()

    def tearDown(self):
        self.adapter.clear_table()

    @patch('corehq.apps.userreports.specs.datetime')
    def _check_sample_doc_state(self, expected_indicators, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        self.adapter.refresh_table()
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
            self.pillow.rebuild_table(get_indicator_adapter(self.config))

    @patch('corehq.apps.userreports.specs.datetime')
    def test_change_transport(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @patch('corehq.apps.userreports.specs.datetime')
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
        self.adapter.refresh_table()
        # make sure we saved rows to the table for everything
        self.assertEqual(len(bad_ints), self.adapter.get_query_object().count())

    @patch('corehq.apps.userreports.specs.datetime')
    def test_basic_doc_processing(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @patch('corehq.apps.userreports.specs.datetime')
    def test_not_relevant_to_domain(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        sample_doc['domain'] = 'not-this-domain'
        self.pillow.process_change(doc_to_change(sample_doc))
        self.adapter.refresh_table()
        self.assertEqual(0, self.adapter.get_query_object().count())

    @patch('corehq.apps.userreports.specs.datetime')
    def test_process_doc_from_couch(self, datetime_mock):
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
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)
        case.delete()

    @patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_process_doc_from_sql(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        since = self.pillow.get_change_feed().get_latest_offsets()

        # save case to DB - should also publish to kafka
        case = _save_sql_case(sample_doc)

        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)

        CaseAccessorSQL.hard_delete_cases(case.domain, [case.case_id])

    @patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_process_deleted_doc_from_sql(self, datetime_mock):
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
        self.adapter.refresh_table()
        self.assertEqual(0, self.adapter.get_query_object().count())

        CaseAccessorSQL.hard_delete_cases(case.domain, [case.case_id])

    @patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_process_filter_no_longer_pass(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.pillow.process_change(doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

        sample_doc['type'] = 'wrong_type'

        self.pillow.process_change(doc_to_change(sample_doc))
        self.adapter.refresh_table()

        self.assertEqual(0, self.adapter.get_query_object().count())

    @patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_check_if_doc_exist(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        self.assertFalse(self.adapter.doc_exists(sample_doc))

        self.pillow.process_change(doc_to_change(sample_doc))

        self.assertIs(self.adapter.doc_exists(sample_doc), True)


@override_settings(OVERRIDE_UCR_BACKEND=UCR_ES_BACKEND)
class IndicatorPillowTestES(IndicatorPillowTest):
    pass


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ProcessRelatedDocTypePillowTest(TestCase):
    domain = 'bug-domain'

    @softer_assert()
    def setUp(self):
        self.pillow = get_kafka_ucr_pillow(topics=['case-sql'])
        self.config = get_data_source_with_related_doc_type()
        self.config.save()
        self.adapter = get_indicator_adapter(self.config)

        self.pillow.bootstrap(configs=[self.config])
        with trap_extra_setup(KafkaUnavailableError):
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

    def test_process_doc_from_sql_stale(self):
        '''
        Ensures that when you update a case that the changes are reflected in
        the UCR table.

        http://manage.dimagi.com/default.asp?245341
        '''

        for i in range(3):
            since = self.pillow.get_change_feed().get_latest_offsets()
            form, cases = self._post_case_blocks(i)
            with self.assertNumQueries(12):
                self.pillow.process_changes(since=since, forever=False)
            rows = self.adapter.get_query_object()
            self.assertEqual(rows.count(), 1)
            row = rows[0]
            self.assertEqual(int(row.parent_property), i)
            errors = PillowError.objects.filter(doc_id='child-id', pillow=self.pillow.pillow_id)
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
        self.pillow1 = get_kafka_ucr_pillow(topics=['case-sql'])
        self.pillow2 = get_kafka_ucr_pillow(topics=['case-sql'])
        self.pillow1.bootstrap(configs=[config1])
        self.pillow2.bootstrap(configs=self.configs)
        with trap_extra_setup(KafkaUnavailableError):
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

    def _test_pillow(self, pillow, since):
        with self.assertNumQueries(12):
            pillow.process_changes(since=since, forever=False)

    def test_reuse_cache(self):
        # tests that these two pillows make the same number of DB calls even
        # though pillow2 has an extra config
        since1 = self.pillow1.get_change_feed().get_latest_offsets()
        since2 = self.pillow2.get_change_feed().get_latest_offsets()
        form, cases = self._post_case_blocks()

        self._test_pillow(self.pillow1, since1)
        self._test_pillow(self.pillow2, since2)

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
        cls.pillow = get_kafka_ucr_pillow()
        cls.config = get_data_source_with_related_doc_type()
        cls.config.asynchronous = True
        cls.config.save()
        cls.adapter = get_indicator_adapter(cls.config)

        cls.pillow.bootstrap(configs=[cls.config])
        with trap_extra_setup(KafkaUnavailableError):
            cls.pillow.get_change_feed().get_latest_offsets()

    @classmethod
    def tearDownClass(cls):
        cls.config.delete()
        cls.adapter.drop_table()
        delete_all_cases()
        delete_all_xforms()
        super(AsyncIndicatorTest, cls).tearDownClass()

    def tearDown(self):
        AsyncIndicator.objects.all().delete()

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

    @patch('corehq.apps.userreports.tasks._get_config')
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


@override_settings(OVERRIDE_UCR_BACKEND=UCR_SQL_BACKEND)
class StaticKafkaIndicatorPillowTest(TestCase):

    def setUp(self):
        self.pillow = get_kafka_ucr_static_pillow()

    def tearDown(self):
        for adapter in self.pillow._processor.table_adapters_by_domain.values():
            adapter.drop_table()

    @patch(
        'corehq.apps.userreports.pillow.'
        'ConfigurableReportTableManagerMixin.get_all_configs',
        MagicMock(return_value=[]))
    @patch(
        'corehq.apps.userreports.pillow.'
        'ConfigurableReportTableManagerMixin.rebuild_tables_if_necessary',
        MagicMock(return_value=None))
    def test_bootstrap_can_be_called(self):
        self.pillow.bootstrap()


@override_settings(OVERRIDE_UCR_BACKEND=UCR_ES_BACKEND)
class StaticKafkaIndicatorPillowTestES(StaticKafkaIndicatorPillowTest):
    pass


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


class RebuildTableTest(TestCase):
    """This test is pretty fragile because in UCRs we have a global metadata
    object that sqlalchemy uses to keep track of tables and indexes. I've attempted
    to work around it here, but it feels a little nasty
    """

    def tearDown(self):
        self.adapter.drop_table()
        self.config.delete()

    def _get_config(self, extra_id):
        config = get_sample_data_source()
        config.table_id = config.table_id + extra_id
        return config

    def _setup_data_source(self, extra_id):
        self.config = self._get_config(extra_id)
        self.config.save()
        pillow = get_kafka_ucr_pillow()
        pillow.bootstrap([self.config])
        self.adapter = get_indicator_adapter(self.config)
        self.engine = self.adapter.engine

    def test_add_index(self):
        # build the table without an index
        self._setup_data_source('add_index')

        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(len(insp.get_indexes(table_name)), 0)

        # add the index to the config
        config = self._get_config('add_index')
        self.addCleanup(config.delete)
        config.configured_indicators[0]['create_index'] = True
        config.save()
        adapter = get_indicator_adapter(config)

        # mock rebuild table to ensure the table isn't rebuilt when adding index
        pillow = get_kafka_ucr_pillow()
        pillow.processors[0].rebuild_table = MagicMock()
        pillow.bootstrap([config])
        self.assertFalse(pillow.processors[0].rebuild_table.called)
        engine = adapter.engine
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(len(insp.get_indexes(table_name)), 1)

    def test_add_non_nullable_column(self):
        self._setup_data_source('add_non_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # add the column to the config
        config = self._get_config('add_non_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append({
            "column_id": "new_date",
            "type": "raw",
            "display_name": "new_date opened",
            "datatype": "datetime",
            "property_name": "other_opened_on",
            "is_nullable": False
        })
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the table is rebuilt
        pillow = get_kafka_ucr_pillow()
        pillow.processors[0].rebuild_table = MagicMock()
        pillow.bootstrap([config])
        self.assertTrue(pillow.processors[0].rebuild_table.called)
        # column doesn't exist because rebuild table was mocked
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # Another time without the mock to ensure the column is there
        pillow = get_kafka_ucr_pillow()
        pillow.bootstrap([config])
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1
        )

    def test_add_nullable_column(self):
        self._setup_data_source('add_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # add the column to the config
        config = self._get_config('add_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append({
            "column_id": "new_date",
            "type": "raw",
            "display_name": "new_date opened",
            "datatype": "datetime",
            "property_name": "other_opened_on",
            "is_nullable": True
        })
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the column is added without rebuild table
        pillow = get_kafka_ucr_pillow()
        pillow.processors[0].rebuild_table = MagicMock()
        pillow.bootstrap([config])
        self.assertFalse(pillow.processors[0].rebuild_table.called)
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1
        )
