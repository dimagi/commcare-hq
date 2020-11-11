from testil import eq

from ..corrupt_couch import find_missing_ids


def test_find_missing_ids():
    def test(result_sets, expected_missing, expected_tries):
        def get_ids():
            while len(results) > 1:
                return results.pop()
            return results[0]

        results = list(reversed(result_sets))
        missing, tries = find_missing_ids(get_ids)
        eq(missing, expected_missing)
        eq(tries, expected_tries)

    yield test, [{1, 2}], set(), 6
    yield test, [{1, 2}, {1, 3}, {2, 3}], {1, 2, 3}, 8
    yield test, [{1, 2}, {1, 3}, {1, 3}, {1, 3}, {1, 3}, {2, 3}], {1, 2, 3}, 11
    yield test, [{1, 2}] + [{1, 3}] * 6 + [{2, 3}], {2, 3}, 7
