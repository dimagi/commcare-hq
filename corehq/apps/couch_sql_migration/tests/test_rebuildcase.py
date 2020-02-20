from datetime import datetime

from testil import Config, eq

from .. import rebuildcase as mod


def test_should_sort_sql_transactions():
    def test(sql_form_ids, couch_form_ids, expect):
        sql_case = Config(
            transactions=[Config(form_id=x, details={}) for x in sql_form_ids]
        )
        couch_json = {"actions": [{"xform_id": x} for x in couch_form_ids]}
        print(sql_case)
        print(couch_json)
        eq(mod.should_sort_sql_transactions(sql_case, couch_json), expect)

    yield test, "abc", "abc", False
    yield test, "abc", "aabbcc", False
    yield test, "abc", "acb", True
    yield test, "abcd", "acb", False
    yield test, "abd", "acb", False


def test_update_transaction_order():
    def print_tx(label, txx):
        print(f"transactions {label} update")
        for tx in txx:
            print(f"  {tx.id}  {tx.form_id: <1}  {tx.server_date}")

    def to_date(chr):
        return dx((ord("z") + 1) if chr == " " else ord(chr))

    def test(sql_form_ids, couch_form_ids, expect=None, n_changes=0):
        if expect is None:
            expect = sql_form_ids
        tx_updates = []
        sql_case = Config(
            transactions=[
                Config(id=i, form_id=x.strip(), server_date=to_date(x), details={})
                for i, x in enumerate(sql_form_ids)
            ],
            track_update=lambda tx: tx_updates.append(tx),
        )
        couch_json = {"actions": [{"xform_id": x.strip()} for x in couch_form_ids]}
        print("couch case", couch_json)
        print_tx("before", sql_case.transactions)
        txx, server_dates = mod.update_transaction_order(sql_case, couch_json)
        print_tx("after", txx)
        eq("".join([tx.form_id if tx.form_id else " " for tx in txx]), expect)
        eq(len(server_dates), n_changes, server_dates)
        eq(len(tx_updates), n_changes, tx_updates)

    yield test, "abc", "abc"
    yield test, "abc ", "abc"
    yield test, "abc", "aabbcc"
    yield test, "abc", "acb", "acb", 1
    yield test, "abc ", "a c b", "acb ", 1


def test_iter_ascending_dates():
    def test(indices, expect):
        dates = [dx(i) for i in indices]
        actual_deltas = deltas(mod.iter_ascending_dates(dates))
        expect_deltas = deltas(dx(i) for i in expect)
        assert mod.is_strictly_ascending(expect_deltas), expect_deltas
        eq(actual_deltas, expect_deltas)

    yield test, [0, 1], [0, 1]
    yield test, [0, 10, 20], [0, 10, 20]
    yield test, [30, 10, 20], [9, 10, 20]
    yield test, [30, 30, 30, 10, 20], [7, 8, 9, 10, 20]
    yield test, [1, 3, 3, 3, 3, 2], [1, 1.2, 1.4, 1.6, 1.8, 2]
    yield test, [0, 20, 10], [0, 5, 10]
    yield test, [0, 10, 20, 10], [0, 10, 20, 21]
    yield test, [40, 50, 60, 70, 10, 20, 30], [40, 50, 60, 70, 71, 72, 73]


def test_longest_increasing_subsequence_indices():
    def test(seq, expect):
        eq(mod.longest_increasing_subsequence_indices(seq), expect)

    yield test, [], []
    yield test, [2], [0]
    yield test, [7, 2], [1]
    yield test, [3, 7], [0, 1]
    yield test, [3, 6, 9], [0, 1, 2]
    yield test, [3, 9, 6], [0, 2]
    yield test, [3, 6, 6], [0, 2]
    yield test, [3, 6, 6, 6, 6, 9], [0, 4, 5]
    yield test, [7, 2, 6, 4, 5, 1], [1, 3, 4]
    yield test, [18, 12, 17, 16, 14, 15, 16, 11], [1, 4, 5, 6]


def dx(minutes_since_epoch):
    return datetime.fromtimestamp(minutes_since_epoch * 60)


def deltas(dates, d0=dx(0)):
    return [str(d - d0) for d in dates]
