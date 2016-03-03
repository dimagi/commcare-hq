from copy import copy
import decimal
import uuid
from django.test import TestCase, SimpleTestCase, override_settings
from mock import patch
from datetime import datetime, timedelta
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import post_case_blocks
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.userreports.exceptions import StaleRebuildError
from corehq.apps.userreports.pillow import ConfigurableIndicatorPillow, REBUILD_CHECK_INTERVAL, \
    ConfigurableReportTableManagerMixin, get_kafka_ucr_pillow
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_doc_and_indicators
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.util.decorators import temporarily_enable_toggle
from corehq.util.test_utils import softer_assert
from corehq.toggles import KAFKA_UCRS
from corehq.util.context_managers import drop_connected_signals
from pillowtop.feed.interface import Change, ChangeMeta
from testapps.test_pillowtop.utils import get_current_kafka_seq


class ConfigurableReportTableManagerTest(SimpleTestCase):

    def test_needs_bootstrap_on_initialization(self):
        table_manager = ConfigurableReportTableManagerMixin()
        self.assertTrue(table_manager.needs_bootstrap())

    def test_bootstrap_sets_time(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin()
        table_manager.bootstrap([])
        after_now = datetime.utcnow() + timedelta(microseconds=1)
        self.assertTrue(table_manager.bootstrapped)
        self.assertTrue(before_now < table_manager.last_bootstrapped)
        self.assertTrue(after_now > table_manager.last_bootstrapped)
        self.assertFalse(table_manager.needs_bootstrap())

    def test_needs_bootstrap_window(self):
        before_now = datetime.utcnow() - timedelta(microseconds=1)
        table_manager = ConfigurableReportTableManagerMixin()
        table_manager.bootstrap([])
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL - 5)
        self.assertFalse(table_manager.needs_bootstrap())
        table_manager.last_bootstrapped = before_now - timedelta(seconds=REBUILD_CHECK_INTERVAL)
        self.assertTrue(table_manager.needs_bootstrap())


class IndicatorPillowTestBase(TestCase):

    def setUp(self):
        self.config = get_sample_data_source()
        self.config.save()
        self.adapter = IndicatorSqlAdapter(self.config)
        self.fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)

    def tearDown(self):
        self.config.delete()
        self.adapter.drop_table()

    @patch('corehq.apps.userreports.specs.datetime')
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


class IndicatorPillowTest(IndicatorPillowTestBase):

    @softer_assert
    def setUp(self):
        super(IndicatorPillowTest, self).setUp()
        self.pillow = ConfigurableIndicatorPillow()
        self.pillow.bootstrap(configs=[self.config])

    def test_stale_rebuild(self):
        later_config = copy(self.config)
        later_config.save()
        self.assertNotEqual(self.config._rev, later_config._rev)
        with self.assertRaises(StaleRebuildError):
            self.pillow.rebuild_table(IndicatorSqlAdapter(self.config))

    @patch('corehq.apps.userreports.specs.datetime')
    def test_change_transport(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.change_transport(sample_doc)
        self._check_sample_doc_state(expected_indicators)

    @patch('corehq.apps.userreports.specs.datetime')
    def test_rebuild_indicators(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        self.config.save()
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        CommCareCase.get_db().save_doc(sample_doc)
        rebuild_indicators(self.config._id)
        self._check_sample_doc_state(expected_indicators)

    def test_bad_integer_datatype(self):
        self.config.save()
        bad_ints = ['a', '', None]
        for bad_value in bad_ints:
            self.pillow.change_transport({
                '_id': uuid.uuid4().hex,
                'doc_type': 'CommCareCase',
                'domain': 'user-reports',
                'type': 'ticket',
                'priority': bad_value
            })
        # make sure we saved rows to the table for everything
        self.assertEqual(len(bad_ints), self.adapter.get_query_object().count())


class KafkaIndicatorPillowTest(IndicatorPillowTestBase):
    dependent_apps = [
        'couchforms', 'pillowtop', 'corehq.couchapps', 'corehq.apps.tzmigration',
        'corehq.form_processor', 'corehq.sql_accessors', 'corehq.sql_proxy_accessors',
        'casexml.apps.case', 'casexml.apps.phone'
    ]

    @softer_assert
    def setUp(self):
        super(KafkaIndicatorPillowTest, self).setUp()
        self.pillow = get_kafka_ucr_pillow()
        self.pillow.bootstrap(configs=[self.config])

    @patch('corehq.apps.userreports.specs.datetime')
    @temporarily_enable_toggle(KAFKA_UCRS, 'user-reports')
    def test_basic_doc_processing(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)
        self.pillow.processor(_doc_to_change(sample_doc))
        self._check_sample_doc_state(expected_indicators)

    @patch('corehq.apps.userreports.specs.datetime')
    @temporarily_enable_toggle(KAFKA_UCRS, 'user-reports')
    def test_process_doc_from_couch(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        # make sure case is in DB
        case = CommCareCase.wrap(sample_doc)
        with drop_connected_signals(case_post_save):
            case.save()

        # send to kafka
        since = get_current_kafka_seq(topics.CASE)
        producer.send_change(topics.CASE, _doc_to_change(sample_doc).metadata)

        # run pillow and check changes
        self.pillow.process_changes(since={topics.CASE: since}, forever=False)
        self._check_sample_doc_state(expected_indicators)
        case.delete()

    @patch('corehq.apps.userreports.specs.datetime')
    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @temporarily_enable_toggle(KAFKA_UCRS, 'user-reports')
    def test_process_doc_from_sql(self, datetime_mock):
        datetime_mock.utcnow.return_value = self.fake_time_now
        sample_doc, expected_indicators = get_sample_doc_and_indicators(self.fake_time_now)

        since = self.pillow.get_change_feed().get_current_offsets()

        # save case to DB - should also publish to kafka
        case = _save_sql_case(sample_doc)

        # run pillow and check changes
        self.pillow.process_changes(since=since, forever=False)
        self._check_sample_doc_state(expected_indicators)

        CaseAccessorSQL.hard_delete_cases(case.domain, [case.case_id])


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


def _doc_to_change(doc):
    return Change(
        id=doc['_id'],
        sequence_id='0',
        document=doc,
        metadata=ChangeMeta(
            document_id=doc['_id'],
            data_source_type=data_sources.COUCH,
            data_source_name=CommCareCase.get_db().dbname,
            document_type=doc['doc_type'],
            document_subtype=doc['type'],
            domain=doc['domain'],
            is_deletion=False,
        )
    )


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
