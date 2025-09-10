from functools import wraps
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from gevent.lock import BoundedSemaphore


class TTLCache:
    """LRU cache for UCR data source adapters

    Loads and stores adapters by domain. Can be refreshed to update
    changed adapters and remove stale entries based on the last time
    they were accessed.

    :param iter_adapters: A callable that takes a domain and returns an
        iterable of (domain, adapter) pairs. This callable must have the
        signature (domain=None, *, since=None) where only one argument
        is provided to each call. When a `domain` is provided, it will
        yield adapters for the domain as well as any other domains that
        use the same adapter. When `since` is provided, it will yield
        adapters that have changed since that time.
    :param timeout: Time in seconds after which stale entries are removed.
        Defaults to 48 hours.
    """
    TTL_48_HOURS = 48 * 60 * 60  # in seconds

    def __init__(self, iter_adapters, adapter_cache=None, timeout=TTL_48_HOURS):
        self.iter_adapters = iter_adapters
        self.domain_last_seen = {}
        self.adapters = adapter_cache or AdapterCache()
        self.timeout = timeout
        self.last_refresh = datetime.now(UTC)

    def get_adapters(self, domain):
        """Get all adapters for the given domain from the cache

        Adapters will be loaded using iter_adapters if there is no entry
        for the domain in the local cache.
        """
        self.domain_last_seen[domain] = datetime.now(UTC)
        adapters = self.adapters.get(domain)
        return self._load_adapters(domain) if adapters is None else adapters

    def _load_adapters(self, domain):
        now = datetime.now(UTC)
        for domain_, adapter in self.iter_adapters(domain):
            if adapter.is_active:
                self.adapters.add(domain_, adapter)
                self.domain_last_seen[domain_] = now
        return self.adapters[domain]

    @wraps(_load_adapters)
    def _load_adapters(self, domain):
        # locking decorator for _load_adapters defined above
        lock = self.adapters.locks[domain]
        while domain not in self.adapters:
            if lock.acquire(blocking=False):
                try:
                    return self._load_adapters.__wrapped__(self, domain)
                finally:
                    lock.release()
            lock.wait()  # wait for concurrent load to finish
        return self.adapters[domain]

    def refresh(self):
        """Reload changed adapters and prune stale entries from the cache"""
        now = datetime.now(UTC)
        last_refresh, self.last_refresh = self.last_refresh, now
        cutoff = now - timedelta(seconds=self.timeout)
        for domain, last_seen in list(self.domain_last_seen.items()):
            if last_seen < cutoff:
                self.adapters.discard(domain)
                self.domain_last_seen.pop(domain, None)

        updated = defaultdict(set)
        for domain, adapter in self.iter_adapters(since=last_refresh):
            if not adapter.is_active:
                updated[adapter.config_id] = set()
            elif domain in self.adapters:
                self.adapters.add(domain, adapter)
                updated[adapter.config_id].add(domain)

        # Remove adapters from domains that no longer reference them.
        # Only needed for RegistryDataSourceTableManager,
        # which can have multiple domains per adapter.
        for config_id, updated_domains in updated.items():
            for domain in self.adapters.entries.keys() - updated_domains:
                self.adapters.entries[domain].pop(config_id, None)

    @wraps(refresh)
    def refresh(self):
        # locking decorator for refresh defined above
        lock = self.adapters.refresh_lock
        if lock.acquire(blocking=False):
            try:
                self.refresh.__wrapped__(self)
            finally:
                lock.release()

    def remove(self, domain, adapter):
        """Remove adapter from domain's cached adapters."""
        self.adapters.discard(domain, adapter)


class MigrationCache:
    """A migration adapter cache that loads all adapters into memory"""

    # all adapters are associated with a single key (None) in the adapter cache

    def __init__(self, iter_adapters, timeout='IGNORED'):
        self.iter_adapters = iter_adapters
        self.adapters = AdapterCache()
        self.last_refresh = datetime.now(UTC)

    def get_adapters(self):
        """Get all adapters from the cache"""
        adapters = self.adapters.get(None)
        return self._load_adapters() if adapters is None else adapters

    def _load_adapters(self):
        for domain_, adapter in self.iter_adapters():
            if adapter.is_active:
                self.adapters.add(None, adapter)
        return self.adapters[None]

    def refresh(self):
        """Reload changed adapters"""
        last_refresh, self.last_refresh = self.last_refresh, datetime.now(UTC)
        for domain, adapter in self.iter_adapters(since=last_refresh):
            if adapter.is_active:
                self.adapters.add(None, adapter)
            else:
                self.adapters.discard(None, adapter)


class AdapterCache:
    """Low-level UCR data source adapter cache data structure

    Thin wrapper of defaultdict where entries maintain a unique set of
    adapters keyed on `adapter.config_id`.
    """

    def __init__(self):
        self.entries = defaultdict(dict)
        self.locks = defaultdict(BoundedSemaphore)
        self.refresh_lock = BoundedSemaphore()

    def get(self, domain):
        """Return a list of adapters for domain, None if there are none.

        Does not mutate the cache.
        """
        entry = self.entries.get(domain)
        return None if entry is None else list(entry.values())

    def __getitem__(self, domain):
        """Return a list of adapters for domain

        An empty set of adapters will be added to the cache for domain
        if there is no existing entry.
        """
        return list(self.entries[domain].values())

    def __contains__(self, domain):
        """Return true if the cache contains an entry for domain"""
        return domain in self.entries

    def add(self, domain, adapter):
        """Add adapter for domain

        The adapter will replace an existing adapter with the same
        `config_id` if it exists.
        """
        self.entries[domain][adapter.config_id] = adapter

    def discard(self, domain, adapter=None):
        """Discard adapter(s) for domain."""
        if adapter is None:
            self.entries.pop(domain, None)
            self.locks.pop(domain, None)
        else:
            self.entries[domain].pop(adapter.config_id, None)
