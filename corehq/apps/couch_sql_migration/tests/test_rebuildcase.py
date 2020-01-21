from datetime import datetime

from testil import Config, eq

from .. import rebuildcase as mod


def test_is_action_order_equal():
    def test(sql_form_ids, couch_form_ids, expect):
        sql_case = Config(
            transactions=[Config(form_id=x) for x in sql_form_ids]
        )
        couch_json = {
            "actions": [{"xform_id": x} for x in couch_form_ids]
        }
        print(sql_case)
        print(couch_json)
        eq(mod.is_action_order_equal(sql_case, couch_json), expect)

    yield test, "abc", "abc", True
    yield test, "abc", "aabbcc", True
    yield test, "abc", "acb", False


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
