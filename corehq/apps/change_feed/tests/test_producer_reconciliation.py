from nose.tools import assert_equal, assert_true

from corehq.apps.change_feed.management.commands.reconcile_producer_logs import (
    Reconciliation,
)
from corehq.apps.change_feed.producer import (
    CHANGE_ERROR,
    CHANGE_PRE_SEND,
    CHANGE_SENT,
)


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
    recon.reconcile()
    case_recon = recon.by_doc_type['case']
    assert_true(case_recon.has_results())
    assert_equal(case_recon.get_results(), {
        'sent_count': 3,
        'persistent_error_count': 1,
        'unaccounted_for': 2,
        'unaccounted_for_ids': {'1', '5'},
    })
    assert_equal(case_recon.errors, {'b': '2'})
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
    recon.reconcile()
    case_recon = recon.by_doc_type['case']
    assert_true(case_recon.has_results())
    assert_equal(case_recon.get_results(), {
        'sent_count': 3,
        'persistent_error_count': 1,
        'unaccounted_for': 0,
        'unaccounted_for_ids': set(),
    })
    assert_equal(case_recon.errors, {'f': '5'})
