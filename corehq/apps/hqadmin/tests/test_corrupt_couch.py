import pytest
from testil import eq

from ..corrupt_couch import find_missing_ids


@pytest.mark.parametrize("result_sets, expected_missing, expected_tries, min_tries", [
    ([{1, 2}], set(), 5, 5),
    ([{1, 2}], set(), 6, 6),
    ([{1, 2}], set(), 10, 10),
    ([{1, 2}, {1, 3}, {2, 3}], {1, 2, 3}, 7, 5),
    ([{1, 2}, {1, 3}, {1, 3}, {1, 3}, {1, 3}, {2, 3}], {1, 2, 3}, 10, 5),
    ([{1, 2}] + [{1, 3}] * 5 + [{2, 4}], {2, 3}, 6, 5),
    ([{1, 2}] + [{1, 3}] * 10 + [{2, 4}], {2, 3}, 11, 10),
])
def test_find_missing_ids(result_sets, expected_missing, expected_tries, min_tries):
    def get_ids():
        while len(results) > 1:
            return results.pop()
        return results[0]

    results = list(reversed(result_sets))
    missing, tries = find_missing_ids(get_ids, min_tries)
    eq(missing, expected_missing)
    eq(tries, expected_tries)
