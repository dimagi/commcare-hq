from django.core.cache import cache

from corehq.util.quickcache import quickcache


class Gauge:
    """
    The class is designed to track a bunch of related values.
    For example, if we want to track pillow lag,
    feature_key can be the topic that pillow is listening to
    then all the partions for that topic would be scopes whose value we want to track and analyse.
    Any mathematical operation can be performed on the values.
    """
    def __init__(self, feature_key, scope_fn, timeout=8 * 60):
        """
        :param feature_key: ``str`` Unique string that will identify the Gauge
        :param scope_fn: ``function`` Function that will be used to get scopes that are to be tracked
        :param timeout: ``int`` how many seconds the reported value should remain in cache.
        """
        self.feature_key = feature_key
        self.timeout = timeout
        self.scopes = scope_fn(feature_key)

    def report(self, tracked_key, observerd_value):
        """
        :param tracked_key: ``str`` A key that identifies the tracked event
        :param observerd_value: ``float`` The value of the tracked event
        Saves the observed value for the tracked key and also updates last reported time.
        """
        assert tracked_key in self.scopes, f"{tracked_key} not in the following scopes {self.scopes}"

        cache.set(self._tracked_event_cache_key(tracked_key), observerd_value, timeout=self.timeout)

        cache.set(self._last_reported_timestamp_key, datetime.now(tz=timezone.utc), timeout=self.timeout)

    @quickcache(['self.feature_key'], timeout=5 * 60, memoize_timeout=60)
    def get_values(self):
        """
        returns a list of all the reported values for
        all the scopes for the give feature key.
        """
        all_cache_keys = [self._tracked_event_cache_key(key) for key in self.scopes]
        all_observed_values = cache.get_many(all_cache_keys)
        return list(all_observed_values.values())

    def _tracked_event_cache_key(self, tracked_key):
        return f'{self.__class__}-{tracked_key}-gauge-key'

    @property
    def _last_reported_timestamp_key(self):
        return f'{self.__class__}-{self.feature_key}-last-reported'

    def get_last_reported_time(self):
        "returns the last time when the lag was reported or will return ``datetime.min`` if not reported yet"
        return cache.get(self._last_reported_timestamp_key, datetime.min)

    def max(self):
        """
        return max lag for a given topic
        """
        values = self.get_values()
        return max(values) if values else None

    def min(self):
        """
        return min lag for a given topic
        """
        values = self.get_values()
        return min(values) if values else None

    def avg(self):
        """
        return average lag for a given topic
        """
        values = self.get_values()
        return sum(values) / len(values) if values else None


case_pillow_lag_gauge = Gauge(feature_key=CASE_SQL, scope_fn=get_all_kafka_partitons_for_topic)
