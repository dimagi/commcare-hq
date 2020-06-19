import logging
from contextlib import contextmanager
from datetime import timedelta

from dimagi.utils.couch import acquire_lock, release_lock
from dimagi.ext.jsonobject import DictProperty, StringProperty

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.models import RebuildWithReason

log = logging.getLogger(__name__)


def rebuild_and_diff_cases(sql_case, couch_case, original_couch_case, diff, dd_count):
    """Try rebuilding SQL case and save if rebuild resolves diffs

    :param sql_case: CommCareCaseSQL object.
    :param couch_case: JSON-ified version of CommCareCase.
    :param diff: function to produce diffs between couch and SQL case JSON.
    :param dd_count: metrics recording counter function.
    :returns: list of diffs returned by `diff(couch_case, rebuilt_case_json)`
    """
    from .casediff import is_case_patched
    lock = CommCareCaseSQL.get_obj_lock_by_id(sql_case.case_id)
    acquire_lock(lock, degrade_gracefully=False)
    try:
        if should_sort_sql_transactions(sql_case, couch_case):
            new_case = rebuild_case_with_couch_action_order(sql_case, couch_case)
            dd_count("commcare.couchsqlmigration.case.rebuild.sql.sort")
        else:
            new_case = rebuild_case(sql_case)
            dd_count("commcare.couchsqlmigration.case.rebuild.sql")
        sql_json = new_case.to_json()
        diffs = diff(couch_case, sql_json)
        if diffs:
            if couch_case != original_couch_case:
                diffs = diff(original_couch_case, sql_json)
            if not diffs or is_case_patched(sql_case.case_id, diffs):
                log.info("original Couch case matches rebuilt SQL case: %s", sql_case.case_id)
                diffs = []
        if not diffs:
            # save case only if rebuild resolves diffs
            CaseAccessorSQL.save_case(new_case)
    finally:
        release_lock(lock, degrade_gracefully=True)
    return sql_json, diffs


def should_sort_sql_transactions(sql_case, couch_json):
    """Check if sql and couch cases had forms applied in the same order

    :param sql_case: `CommCareCaseSQL` object.
    :param couch_json: `CommCareCase` JSON (dict, not string).
    :returns: True if (trans)action order matches else false.
    """
    def dedup(items):
        return dict.fromkeys(items)
    sql_ids = dedup(t.form_id for t in sql_case.transactions if t.form_id)
    couch_ids = dedup(a["xform_id"] for a in couch_json["actions"] if a["xform_id"])
    return sql_ids == couch_ids and list(sql_ids) != list(couch_ids)


def rebuild_case_with_couch_action_order(sql_case, couch_case):
    """Sort transactions to match Couch actions and rebuild case

    This does not save the case. This function should be wrapped in a
    case lock if the case will be saved afterward.
    """
    transactions, server_dates = update_transaction_order(sql_case, couch_case)
    detail = SortTransactionsRebuild(original_server_dates=server_dates)
    with patch_transactions(sql_case, transactions):
        return rebuild_case(sql_case, detail)


@contextmanager
def patch_transactions(sql_case, transactions):
    def get_transactions(case, updated_xforms=None):
        if case.case_id == sql_case.case_id:
            assert not updated_xforms, (case.case_id, updated_xforms)
            len_before_fetch = len(transactions)
            CaseAccessorSQL.fetch_case_transaction_forms(
                case, transactions, updated_xforms)
            assert len(transactions) == len_before_fetch, (case.case_id, transactions)
            return transactions
        return real_get_transactions(case, updated_xforms)
    real_get_transactions = CaseAccessorSQL.get_case_transactions_by_case_id
    CaseAccessorSQL.get_case_transactions_by_case_id = get_transactions
    try:
        yield
    finally:
        CaseAccessorSQL.get_case_transactions_by_case_id = real_get_transactions


def rebuild_case(sql_case, detail=None):
    """Rebuild SQL case

    This does not save the case. This function should be wrapped in a
    case lock if the case will be saved afterward.
    """
    if detail is None:
        detail = RebuildWithReason(reason=COUCH_SQL_REBUILD_REASON)
    new_case = FormProcessorSQL.hard_rebuild_case(
        sql_case.domain, sql_case.case_id, detail, lock=False, save=False)
    return new_case


def update_transaction_order(sql_case, couch_case):
    """Update SQL case transactions so they match couch actions

    SQL case transactions are sorted by `transaction.server_date`.
    See corehq/sql_accessors/sql_templates/get_case_transactions_by_type.sql
    """
    def sort_key(tx):
        return indices.get(tx.form_id, at_end)

    at_end = len(couch_case["actions"])
    indices = {}
    for i, action in enumerate(couch_case["actions"]):
        form_id = action["xform_id"]
        if form_id and form_id not in indices:
            indices[form_id] = i

    server_dates = {}
    transactions = sorted(sql_case.transactions, key=sort_key)
    old_dates = [t.server_date for t in transactions]
    new_dates = iter_ascending_dates(old_dates)
    for trans, new_date in zip(transactions, new_dates):
        if trans.server_date != new_date:
            server_dates[trans.id] = trans.server_date
            trans.server_date = new_date
            sql_case.track_update(trans)
    return transactions, server_dates


class SortTransactionsRebuild(RebuildWithReason):
    _REASON = 'Couch to SQL: sort transactions'
    reason = StringProperty(default=_REASON)
    original_server_dates = DictProperty()


COUCH_SQL_REBUILD_REASON = "Couch to SQL migration"


def iter_ascending_dates(dates):
    """Adjust unordered dates so they are in ascending order

    Adjust a minimal number of dates so the resulting sequence of dates
    is in ascending order. Each non-ascending date is replaced with a
    new date that falls between the dates before and after in the
    sequence.

    :param dates: Sequence of `datetime` objects.
    :returns: Sequence of `datetime` objects in ascending order.
    """
    if is_strictly_ascending(dates):
        yield from dates
        return

    def getnext(i):
        j = i + 1
        if j in next_cache:
            return next_cache.pop(j)
        if j in keepset:
            next_cache[j] = dates[j], 1
        elif j < len(dates):
            nxt, span = getnext(j)
            next_cache[j] = nxt, (span + 1 if span else None)
        else:
            next_cache[j] = None, None
        return next_cache[j]

    keepset = set(longest_increasing_subsequence_indices(dates))
    next_cache = {}
    prev = None
    minute = timedelta(minutes=1)
    for i, value in enumerate(dates):
        if i not in keepset:
            nxt, span = getnext(i)
            if not nxt:
                value = prev + minute
            elif not prev:
                value = nxt - (minute * span)
            else:
                step = (nxt - prev) / (span + 1)
                value = prev + step
        yield value
        prev = value


def longest_increasing_subsequence_indices(values):
    """Get indices of the longest strictly increasing subsequence of values

    O(n log n) algorithm based on solution form Wikipedia
    https://en.wikipedia.org/wiki/Longest_increasing_subsequence#Efficient_algorithms

    - Use more descriptive variable names.
    - Use < rather than <= when comparing values in binary search
      to make the result strictly increasing (no equal values).

    :param values: A sequence of values.
    :returns: A list of indices.
    """
    if not values:
        return values
    n = len(values)
    predecessor_index = []
    longest_seq_start = [None] * (n + 1)
    longest = 0
    for i, current in enumerate(values):
        # Binary search for the largest positive j <= longest
        # such that values[longest_seq_start[j]] < current
        lo = 1
        hi = longest
        while lo <= hi:
            mid = (lo + hi) // 2
            if values[longest_seq_start[mid]] < current:
                lo = mid + 1
            else:
                hi = mid - 1

        # After searching, lo is 1 greater than the
        # length of the longest prefix of current
        new_longest = lo

        # The predecessor of current is the last index of
        # the subsequence of length new_longest - 1
        predecessor_index.append(longest_seq_start[new_longest - 1])
        longest_seq_start[new_longest] = i

        if new_longest > longest:
            longest = new_longest

    solution = [None] * longest
    k = longest_seq_start[longest]
    for i in range(longest - 1, -1, -1):
        solution[i] = k
        k = predecessor_index[k]
    return solution


def is_strictly_ascending(items):
    return all(a < b for a, b in zip(items, items[1:]))
