from datetime import UTC, datetime

import gevent
import pytest
from attrs import define, field
from gevent.event import Event
from time_machine import travel

from ..adaptercache import AdapterCache, MigrationCache, TTLCache


class TestTTLCache:

    def test_get_adapters(self):
        def iter_adapters(domain=None, *, since=None):
            assert since is None
            yield domain, Adapter(domain)

        with travel('2020-01-01T00:00:00Z', tick=False):
            cache = TTLCache(iter_adapters)

            result = cache.get_adapters('one')
            assert result[0].domain == 'one'
            assert len(result) == 1

        # test local memory cache
        assert cache.get_adapters('one') == result

    def test_get_adapters_with_irrelevant_domain(self):
        def iter_adapters(domain=None, *, since=None):
            assert since is None
            return []
        cache = TTLCache(iter_adapters)

        assert cache.get_adapters('one') == []

    def test_get_adapters_does_not_get_deactivated_adapter(self):
        def iter_adapters(domain=None, *, since=None):
            assert since is None
            yield domain, Adapter(domain, is_active=False)
        cache = TTLCache(iter_adapters)

        assert cache.get_adapters('one') == []

    def test_refresh_removes_stale_entries(self):
        def iter_adapters(domain=None, *, since=None):
            if not since:
                adapter = Adapter(domain)
                yield domain, adapter
                yield 'two', adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            cache = TTLCache(iter_adapters)
            result = cache.get_adapters('one')

        with travel('2020-01-02T00:00:00Z', tick=False):
            cache.refresh()
            assert cache.get_adapters('one') == result
            assert 'two' in cache.adapters

        with travel('2020-01-04T01:00:00Z', tick=False):
            cache.refresh()
            assert 'two' not in cache.adapters
            assert cache.get_adapters('one') != result

    def test_refresh_updates_modified_adapters(self):
        def iter_adapters(domain=None, *, since=None):
            for domain, adapter in adapters.items():
                if since is None or adapter.modified > since:
                    yield domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapter1 = Adapter('one')
            adapters = {'one': adapter1, 'two': adapter1}
            cache = TTLCache(iter_adapters)

            result = cache.get_adapters('one')
            assert cache.get_adapters('two') == result
            assert 'three' not in cache.adapters

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapters['two'] = Adapter('two')
            adapters['three'] = Adapter('three')
            cache.refresh()
            assert cache.get_adapters('one') == result  # no change
            assert cache.get_adapters('two') == [adapter1, adapters['two']]
            # refresh should not load modified adapter that was not cached
            assert 'three' not in cache.adapters

    def test_refresh_removes_adapter_from_domain(self):
        def iter_adapters(domain=None, *, since=None):
            for domain, adapter in adapters.items():
                if since is None or adapter.modified > since:
                    yield domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapter1 = Adapter('one')
            adapters = {'one': adapter1, 'two': adapter1}
            cache = TTLCache(iter_adapters)

            result = cache.get_adapters('one')
            assert cache.get_adapters('two') == result

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapter1.modified = datetime.now(UTC)  # update on refresh
            adapters = {'one': adapter1}
            cache.refresh()
            assert cache.get_adapters('one') == result  # no change
            assert cache.get_adapters('two') == []

    def test_refresh_updates_modified_adapter_where_others_have_not_changed(self):
        def iter_adapters(domain=None, *, since=None):
            for adapter in adapters:
                if since is None or adapter.modified > since:
                    yield adapter.domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapters = [Adapter('one', 0), Adapter('one', 1)]
            cache = TTLCache(iter_adapters)

            assert cache.get_adapters('one') == adapters

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapters[0] = Adapter('one', 0)
            assert cache.get_adapters('one') != adapters
            cache.refresh()
            assert cache.get_adapters('one') == adapters

    def test_refresh_removes_deactivated_adapter(self):
        def iter_adapters(domain=None, *, since=None):
            for domain, adapter in adapters.items():
                if since is None or adapter.modified > since:
                    yield domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapter1 = Adapter('one')
            adapters = {'one': adapter1, 'two': adapter1}
            cache = TTLCache(iter_adapters)

            result = cache.get_adapters('one')
            assert cache.get_adapters('two') == result

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapter1.modified = datetime.now(UTC)
            adapter1.is_active = False
            adapters = {'three': adapter1}
            cache.refresh()
            assert cache.get_adapters('one') == []
            assert cache.get_adapters('two') == []

    def test_remove_adapter(self):
        def iter_adapters(domain=None, *, since=None):
            if since is None or adapter.modified > since:
                yield adapter.domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapter = Adapter('one')
            cache = TTLCache(iter_adapters)
            assert cache.get_adapters('one') == [adapter]

            cache.remove('one', adapter)
            assert cache.get_adapters('one') == []
            cache.refresh()
            assert cache.get_adapters('one') == []

        with travel('2020-01-01T01:00:00Z', tick=False):
            adapter.modified = datetime.now(UTC)
            cache.refresh()
            assert cache.get_adapters('one') == [adapter]

    def test_concurrent_refresh(self):
        def iter_adapters(domain=None, *, since=None):
            if since is not None:
                refreshes.append(1)
                cache.refresh()  # should return immediately, without recursion
            yield adapter.domain, adapter

        refreshes = []
        adapter = Adapter('one')
        cache = TTLCache(iter_adapters)

        cache.refresh()  # should not recurse infinitely
        assert sum(refreshes) == 1

    def test_concurrent_load(self):
        def iter_adapters(domain=None, *, since=None):
            worker = gevent.getcurrent()
            assert worker is worker1, f"{worker} should not iter_adapters"
            iterating.set()
            assert unblock.wait(timeout=2)
            order.append(3)
            yield adapter.domain, adapter

        def do_get(cache, ident, domain):
            assert domain not in cache.adapters
            order.append(ident)
            return cache.get_adapters(domain)

        adapter = Adapter('one')
        adapter_cache = AdapterCache()
        cache = TTLCache(iter_adapters, adapter_cache)
        other = TTLCache(iter_adapters, adapter_cache)
        order = []

        iterating = Event()
        unblock = Event()
        worker1 = gevent.spawn(do_get, cache, 1, 'one')
        assert iterating.wait(timeout=2)

        worker2 = gevent.spawn(do_get, other, 2, 'one')
        gevent.sleep()  # allow worker2 to run until blocked
        assert not worker2.ready(), str(worker2.exception)

        unblock.set()
        gevent.joinall([worker1, worker2], timeout=5)
        assert order == [1, 2, 3]
        assert worker1.get(block=False) == [adapter]
        assert worker2.get(block=False) == [adapter]

    def test_concurrent_load_different_domains(self):
        def iter_adapters(domain=None, *, since=None):
            iterating.set()
            assert unblock.wait(timeout=2)
            order.append(3)
            yield adapter.domain, adapter
            yield 'two', adapter

        def do_get(cache, ident, domain):
            assert domain not in cache.adapters
            order.append(ident)
            return cache.get_adapters(domain)

        adapter = Adapter('one')
        adapter_cache = AdapterCache()
        cache = TTLCache(iter_adapters, adapter_cache)
        other = TTLCache(iter_adapters, adapter_cache)
        order = []

        iterating = Event()
        unblock = Event()

        worker1 = gevent.spawn(do_get, cache, 1, 'one')
        assert iterating.wait(timeout=2)
        iterating.clear()

        worker2 = gevent.spawn(do_get, other, 2, 'two')
        assert iterating.wait(timeout=2)
        assert not worker2.ready(), str(worker2.exception)

        unblock.set()
        gevent.joinall([worker1, worker2], timeout=7)
        assert order == [1, 2, 3, 3]
        # [..., 3, 3] means iter_adapters got called twice concurrently.
        # Not super efficient for RegistryDataSourceTableManager, but
        # should be safe. More efficient than using a single lock for
        # all domains, and far easier to implement than locking on the
        # set of domains associated with all registries known to the
        # domain for which adapters are being loaded.

        assert worker1.get(block=False) == [adapter]
        assert worker2.get(block=False) == [adapter]

    def test_concurrent_load_error(self):
        def iter_adapters(domain=None, *, since=None):
            iterating.set()
            assert unblock.wait(timeout=2)
            if gevent.getcurrent() is worker1:
                raise DatabaseError
            order.append(3)
            yield adapter.domain, adapter

        def do_get(cache, ident, domain):
            assert domain not in cache.adapters
            order.append(ident)
            return cache.get_adapters(domain)

        adapter = Adapter('one')
        adapter_cache = AdapterCache()
        cache = TTLCache(iter_adapters, adapter_cache)
        other = TTLCache(iter_adapters, adapter_cache)
        order = []

        iterating = Event()
        unblock = Event()

        worker1 = gevent.spawn(do_get, cache, 1, 'one')
        assert iterating.wait(timeout=2)

        worker2 = gevent.spawn(do_get, other, 2, 'one')
        assert iterating.wait(timeout=2)
        assert not worker2.ready(), str(worker2.exception)

        unblock.set()
        gevent.joinall([worker1, worker2], timeout=7)
        assert order == [1, 2, 3]
        with pytest.raises(DatabaseError):
            worker1.get(block=False)
        assert worker2.get(block=False) == [adapter]


class TestMigrationCache:

    def test_get_adapters(self):
        def iter_adapters(domain=None, *, since=None):
            for adapter in adapters:
                if since is None or adapter.modified > since:
                    yield adapter.domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapters = [Adapter('one'), Adapter('two')]
            cache = MigrationCache(iter_adapters)
            assert not cache.adapters.entries

            assert cache.get_adapters() == adapters

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapters.append(Adapter('three'))
            cache.refresh()
            assert cache.get_adapters() == adapters

    def test_inactive_adapter(self):
        def iter_adapters(domain=None, *, since=None):
            for adapter in adapters:
                if since is None or adapter.modified > since:
                    yield adapter.domain, adapter

        with travel('2020-01-01T00:00:00Z', tick=False):
            adapters = [Adapter('one'), Adapter('two', is_active=False)]
            cache = MigrationCache(iter_adapters)
            assert not cache.adapters.entries

            assert cache.get_adapters() == adapters[:1]

        with travel('2020-01-02T00:00:00Z', tick=False):
            adapters[0].modified = datetime.now(UTC)
            adapters[0].is_active = False
            cache.refresh()
            assert cache.get_adapters() == []


@define
class Adapter:
    domain = field()
    config_id = field(factory=lambda: next(_ids))
    modified = field(
        factory=lambda: datetime.now(UTC),
        repr=lambda v: v.isoformat(),
    )
    is_active = field(default=True)


class DatabaseError(Exception):
    pass


_ids = iter(range(1_000_000))
