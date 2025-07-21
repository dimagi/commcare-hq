from datetime import UTC, datetime

from attrs import define, field
from freezegun import freeze_time

from ..adaptercache import AdapterCache, MigrationCache, TTLCache


def test_ttl_cache_get_adapters():
    def iter_adapters(domain=None, *, since=None):
        assert since is None
        yield domain, Adapter(domain)

    with freeze_time('2020-01-01T00:00:00Z'):
        cache = TTLCache(iter_adapters, AdapterCache())

        result = cache.get_adapters('one')
        assert result[0].domain == 'one'
        assert len(result) == 1

    # test local memory cache
    assert cache.get_adapters('one') == result


def test_ttl_cache_get_adapters_with_irrelevant_domain():
    def iter_adapters(domain=None, *, since=None):
        assert since is None
        return []
    cache = TTLCache(iter_adapters, AdapterCache())

    assert cache.get_adapters('one') == []


def test_ttl_cache_refresh_removes_stale_entries():
    def iter_adapters(domain=None, *, since=None):
        if not since:
            adapter = Adapter(domain)
            yield domain, adapter
            yield 'two', adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        cache = TTLCache(iter_adapters, AdapterCache())
        result = cache.get_adapters('one')

    with freeze_time('2020-01-02T00:00:00Z'):
        cache.refresh()
        assert cache.get_adapters('one') == result
        assert 'two' in cache.adapters

    with freeze_time('2020-01-04T01:00:00Z'):
        cache.refresh()
        assert 'two' not in cache.adapters
        assert cache.get_adapters('one') != result


def test_ttl_cache_refresh_updates_modified_adapters():
    def iter_adapters(domain=None, *, since=None):
        for domain, adapter in adapters.items():
            if since is None or adapter.modified > since:
                yield domain, adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        adapter1 = Adapter('one')
        adapters = {'one': adapter1, 'two': adapter1}
        cache = TTLCache(iter_adapters, AdapterCache())

        result = cache.get_adapters('one')
        assert cache.get_adapters('two') == result
        assert 'three' not in cache.adapters

    with freeze_time('2020-01-02T00:00:00Z'):
        adapters['two'] = Adapter('two')
        adapters['three'] = Adapter('three')
        cache.refresh()
        assert cache.get_adapters('one') == result  # no change
        assert cache.get_adapters('two') == [adapter1, adapters['two']]
        assert 'three' not in cache.adapters


def test_ttl_cache_refresh_removes_adapter_from_domain():
    def iter_adapters(domain=None, *, since=None):
        for domain, adapter in adapters.items():
            if since is None or adapter.modified > since:
                yield domain, adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        adapter1 = Adapter('one')
        adapters = {'one': adapter1, 'two': adapter1}
        cache = TTLCache(iter_adapters, AdapterCache())

        result = cache.get_adapters('one')
        assert cache.get_adapters('two') == result

    with freeze_time('2020-01-02T00:00:00Z'):
        adapter1.modified = datetime.now(UTC)
        adapters = {'one': adapter1}
        cache.refresh()
        assert cache.get_adapters('one') == result  # no change
        assert cache.get_adapters('two') == []


def test_ttl_cache_refresh_updates_modified_adapter_where_others_have_not_changed():
    def iter_adapters(domain=None, *, since=None):
        for adapter in adapters:
            if since is None or adapter.modified > since:
                yield adapter.domain, adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        adapters = [Adapter('one', 0), Adapter('one', 1)]
        cache = TTLCache(iter_adapters, AdapterCache())

        assert cache.get_adapters('one') == adapters

    with freeze_time('2020-01-02T00:00:00Z'):
        adapters[0] = Adapter('one', 0)
        assert cache.get_adapters('one') != adapters
        cache.refresh()
        assert cache.get_adapters('one') == adapters


def test_ttl_cache_remove_adapter():
    def iter_adapters(domain=None, *, since=None):
        if since is None or adapter.modified > since:
            yield adapter.domain, adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        adapter = Adapter('one')
        cache = TTLCache(iter_adapters, AdapterCache())
        result = cache.get_adapters('one')
        assert result == [adapter]

        cache.remove('one', adapter)
        assert cache.get_adapters('one') == []
        cache.refresh()
        assert cache.get_adapters('one') == []

    with freeze_time('2020-01-01T01:00:00Z'):
        adapter.modified = datetime.now(UTC)
        cache.refresh()
        assert cache.get_adapters('one') == [adapter]


def test_migration_cache():
    def iter_adapters(domain=None, *, since=None):
        for adapter in adapters:
            if since is None or adapter.modified > since:
                yield adapter.domain, adapter

    with freeze_time('2020-01-01T00:00:00Z'):
        adapters = [Adapter('one'), Adapter('two')]
        cache = MigrationCache(iter_adapters, AdapterCache())
        assert not cache.adapters.entries

        assert cache.get_adapters() == adapters

    with freeze_time('2020-01-02T00:00:00Z'):
        adapters.append(Adapter('three'))
        cache.refresh()
        assert cache.get_adapters() == adapters


@define
class Adapter:
    domain = field()
    config_id = field(factory=lambda: next(_ids))
    modified = field(
        factory=lambda: datetime.now(UTC),
        repr=lambda v: v.isoformat(),
    )


_ids = iter(range(1_000_000))
