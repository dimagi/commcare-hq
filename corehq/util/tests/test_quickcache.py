from __future__ import absolute_import, unicode_literals

from testil import eq

from ..quickcache import _quickcache_id


def test_quickcache_id():
    class Request(object):
        pass

    # 2 collisions routinely occur with a sample size of 1M
    SAMPLE_SIZE = 1000
    requests = [Request() for x in range(SAMPLE_SIZE)]
    ids = [_quickcache_id(r) for r in requests]
    eq(ids, [_quickcache_id(r) for r in requests])
    eq({len(id) for id in ids}, {7})
    # safe sanity check, 1% is NOT a reasonable collision rate
    assert len(set(ids)) > SAMPLE_SIZE * .99, (len(set(ids)), SAMPLE_SIZE)
