from testil import eq

from ..corrupt_couch import find_missing_ids


def test_find_missing_ids():
    def test(result_sets, expected_missing, expected_tries, min_tries=5):
        def get_ids():
            while len(results) > 1:
                return results.pop()
            return results[0]

        results = list(reversed(result_sets))
        missing, tries = find_missing_ids(get_ids, min_tries)
        eq(missing, expected_missing)
        eq(tries, expected_tries)

    yield test, [{1, 2}], set(), 5
    yield test, [{1, 2}], set(), 6, 6
    yield test, [{1, 2}], set(), 10, 10
    yield test, [{1, 2}, {1, 3}, {2, 3}], {1, 2, 3}, 7
    yield test, [{1, 2}, {1, 3}, {1, 3}, {1, 3}, {1, 3}, {2, 3}], {1, 2, 3}, 10
    yield test, [{1, 2}] + [{1, 3}] * 5 + [{2, 4}], {2, 3}, 6
    yield test, [{1, 2}] + [{1, 3}] * 10 + [{2, 4}], {2, 3}, 11, 10
