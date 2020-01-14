from datetime import timedelta

from dimagi.ext.jsonobject import DictProperty, StringProperty

from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.backends.sql.update_strategy import (
    _transaction_sort_key_function as transaction_key
)
from corehq.form_processor.models import RebuildWithReason


def is_action_order_equal(sql_case, couch_json):
    """Check if sql and couch cases had forms applied in the same order

    :param sql_case: `CommCareCaseSQL` object.
    :param couch_json: `CommCareCase` JSON (dict, not string).
    :returns: True if (trans)action order matches else false.
    """
    def dedup(items):
        return list(dict.fromkeys(items))
    sql_ids = dedup(t.form_id for t in sql_case.transactions if t.form_id)
    couch_ids = dedup(a["xform_id"] for a in couch_json["actions"] if a["xform_id"])
    return sql_ids == couch_ids


def was_rebuilt(sql_case):
    """Check if most recent case transaction is a sort rebuild"""
    details = sql_case.transactions[-1].details if sql_case.transactions else None
    return details and details["reason"] == SortTransactionsRebuild._REASON


def rebuild_case_with_couch_action_order(sql_case):
    server_dates = update_transaction_order(sql_case)
    detail = SortTransactionsRebuild(original_server_dates=server_dates)
    return FormProcessorSQL.hard_rebuild_case(
        sql_case.domain, sql_case.case_id, detail)


def update_transaction_order(sql_case):
    """Update SQL case transactions so they match couch actions

    SQL case transactions are sorted by `transaction.server_date`.
    See corehq/sql_accessors/sql_templates/get_case_transactions_by_type.sql
    """
    server_dates = {}
    transactions = sorted(sql_case.transactions, key=transaction_key(sql_case))
    old_dates = [t.server_date for t in transactions]
    new_dates = iter_ascending_dates(old_dates)
    for trans, new_date in zip(transactions, new_dates):
        if trans.server_date != new_date:
            server_dates[trans.id] = trans.server_date
            trans.server_date = new_date
            trans.save()
    return server_dates


class SortTransactionsRebuild(RebuildWithReason):
    _REASON = 'Couch to SQL: sort transactions'
    reason = StringProperty(default=_REASON)
    original_server_dates = DictProperty()


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
