from collections import defaultdict

from testil import eq

from corehq.apps.change_feed.partitioners import _n_choose_k_hash


def _test_eq(key, n, k, expected_result):
    eq(_n_choose_k_hash(key, n, k), expected_result)


def test_n_choose_k_hash_consistency():
    yield _test_eq, 'maple', 32, 5, {7, 10, 22, 26, 28}
    yield _test_eq, 'oak', 32, 5, {2, 3, 5, 15, 23}
    yield _test_eq, 'palm', 32, 5, {7, 12, 16, 25, 26}


def test_n_choose_k_hash_edge_cases():
    yield _test_eq, 'zero', 0, 0, set()
    yield _test_eq, 'one', 10, 0, set()
    yield _test_eq, 'two', 0, 10, set()
    yield _test_eq, 'three', 10, 10, set(range(10))
    yield _test_eq, 'four', 5, 10, set(range(5))
    yield _test_eq, None, 5, 10, set(range(5))


def test_n_choose_k_hash_distribution():
    example_keys = set((
        "We hold these truths to be self-evident, that all [people] are created equal, "
        "that they are endowed by their Creator with certain unalienable Rights, "
        "that among these are Life, Liberty and the pursuit of Happiness."
    ).split())

    print(len(example_keys))
    shards_to_keys = defaultdict(list)
    for i in range(5):
        for key in example_keys:
            key_i = f'{key}-{i}'
            shards_to_keys[tuple(sorted(_n_choose_k_hash(key_i, n=32, k=5)))].append(key_i)

    print(shards_to_keys)
    clashes = []
    for shard, keys in shards_to_keys.items():
        if len(keys) > 1:
            clashes.append((keys, shard))

    # (32 choose 5) = 201,376
    # so it is unlikely that there will be any overlap in the chosen set
    # for a small number of different keys
    # There's a 1 in 10 chance that 200 keys will have a clash,
    # which seems high, but if one project is causing trouble at once,
    # the chance that any other project clashes with _that_ one is really low
    assert not clashes, "Clashing outputs: {}".format(
        '; '.join(
            f"{', '.join(keys)} => {shard}"
            for keys, shard in clashes
        )
    )
