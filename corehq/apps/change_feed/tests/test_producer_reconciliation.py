import uuid

from django.test import SimpleTestCase

from kafka.future import Future
from mock import Mock
from nose.tools import assert_equal, assert_true

from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.management.commands.reconcile_producer_logs import (
    Reconciliation,
)
from corehq.apps.change_feed.producer import (
    CHANGE_ERROR,
    CHANGE_PRE_SEND,
    CHANGE_SENT,
    KAFKA_AUDIT_LOGGER,
    ChangeProducer,
)
from corehq.util.test_utils import capture_log_output


class TestKafkaAuditLogging(SimpleTestCase):
    def test_success_synchronous(self):
        self._test_success(auto_flush=True)

    def test_success_asynchronous(self):
        self._test_success(auto_flush=False)

    def test_error_synchronous(self):
        kafka_producer = ChangeProducer()
        future = Future()
        future.get = Mock(side_effect=Exception())
        kafka_producer.producer.send = Mock(return_value=future)

        meta = ChangeMeta(
            document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name'
        )

        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            with self.assertRaises(Exception):
                kafka_producer.send_change(topics.CASE, meta)

        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_ERROR])

    def test_error_asynchronous(self):
        kafka_producer = ChangeProducer(auto_flush=False)
        future = Future()
        kafka_producer.producer.send = Mock(return_value=future)

        meta = ChangeMeta(
            document_id=uuid.uuid4().hex, data_source_type='dummy-type', data_source_name='dummy-name'
        )

        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            kafka_producer.send_change(topics.CASE, meta)
            future.failure(Exception())

        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_ERROR])

    def _test_success(self, auto_flush):
        kafka_producer = ChangeProducer(auto_flush=auto_flush)
        with capture_log_output(KAFKA_AUDIT_LOGGER) as logs:
            meta = ChangeMeta(document_id=uuid.uuid4().hex, data_source_type='dummy-type',
                              data_source_name='dummy-name')
            kafka_producer.send_change(topics.CASE, meta)
            if not auto_flush:
                kafka_producer.flush()
        self._check_logs(logs, meta.document_id, [CHANGE_PRE_SEND, CHANGE_SENT])

    def _check_logs(self, captured_logs, doc_id, events):
        lines = captured_logs.get_output().splitlines()
        self.assertEqual(len(events), len(lines))
        for event, line in zip(events, lines):
            self.assertIn(doc_id, line)
            self.assertIn(event, line)


def test_recon():
    recon = Reconciliation()
    rows = [
        # date, type, doc_type, doc_id, transaction_id
        ('', CHANGE_PRE_SEND, 'case', '1', 'a'),
        ('', CHANGE_SENT, 'case', '1', 'a'),
        ('', CHANGE_PRE_SEND, 'case', '2', 'b'),
        ('', CHANGE_ERROR, 'case', '2', 'b'),
        ('', CHANGE_PRE_SEND, 'case', '3', 'c'),
        ('', CHANGE_PRE_SEND, 'case', '4', 'd'),
        ('', CHANGE_SENT, 'case', '3', 'c'),
        ('', CHANGE_SENT, 'case', '4', 'd'),
        ('', CHANGE_PRE_SEND, 'case', '1', 'e'),
        ('', CHANGE_PRE_SEND, 'case', '5', 'f'),
    ]

    for row in rows:
        recon.add_row(row)

    case_recon = recon.by_doc_type['case']
    assert_true(case_recon.has_results())
    assert_equal(case_recon.get_results(), {
        'transaction_count': 6,
        'persistent_error_count': 1,
        'unaccounted_for': 2,
        'unaccounted_for_ids': {'1', '5'},
    })
    assert_equal(case_recon.error_doc_ids, {'2'})
    return recon


def test_recon_with_freeze():
    recon = test_recon()
    recon.freeze()
    rows = [
        ('', CHANGE_PRE_SEND, 'case', '6', 'g'),
        ('', CHANGE_PRE_SEND, 'case', '2', 'h'),
        ('', CHANGE_SENT, 'case', '1', 'e'),  # reconciles transaction from pre-freeze
        ('', CHANGE_SENT, 'case', '2', 'h'),  # reconciles persistent error from pre-freeze
        ('', CHANGE_ERROR, 'case', '5', 'f'),  # reconciles transaction from pre-freeze
    ]
    for row in rows:
        recon.add_row(row)

    case_recon = recon.by_doc_type['case']
    assert_true(case_recon.has_results())
    assert_equal(case_recon.get_results(), {
        'transaction_count': 6,
        'persistent_error_count': 1,
        'unaccounted_for': 0,
        'unaccounted_for_ids': set(),
    })
    assert_equal(case_recon.error_doc_ids, {'5'})
