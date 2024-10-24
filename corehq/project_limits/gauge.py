from datetime import datetime, time, timedelta, timezone

from django.core.cache import cache

from corehq.apps.change_feed.topics import (
    CASE_SQL,
    get_all_kafka_partitons_for_topic,
)
from corehq.project_limits.models import AVG, PillowLagGaugeDefinition
from corehq.util.quickcache import quickcache


@quickcache(['kafka_topic'], memoize_timeout=60, timeout=24 * 60 * 60)
def get_pillow_throttle_definition(kafka_topic):
    try:
        return PillowLagGaugeDefinition.objects.get(key=kafka_topic)
    except PillowLagGaugeDefinition.DoesNotExist:
        return None


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
        return f'{type(self).__name__}-{tracked_key}-key'

    @property
    def _last_reported_timestamp_key(self):
        return f'{type(self).__name__}-{self.feature_key}-last-reported'

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


class GaugeLimiter:

    def __init__(self, gauge, get_gauge_definition):
        """
        :param gauge: ``Gauge`` An instance of Gauge class
        :param get_gauge_defintions: ``function``
            A function to get config that GaugeLimiter will use to
            figure out throttling conditions.
        """
        self.gauge = gauge
        self.gauge_definition_fn = get_gauge_definition

    def wait(self):
        if not self.allow_usage():
            time.sleep(self.gauge_definition.wait_for_seconds)

    def allow_usage(self):
        """
        Checks for the throttle conditions provided in the Defintion class and evaluates them.
        returns `True` it means that the usage should not be throttled.
                `False` it means that the usage should be throttled.
        """
        if not self.gauge_definition:
            # no throttling if config to throttle is not set.
            return True
        computed_value = None
        if self.gauge_definition.aggregator == AVG:
            computed_value = self.gauge.avg()
        else:
            computed_value = self.gauge.max()
        return computed_value < self.gauge_definition.acceptable_value

    @property
    def gauge_definition(self):
        """
        Should return an instace of subclass of ThrottleDefinition
        """
        return self.gauge_definition_fn(self.gauge.feature_key)


class PillowLagGaugeLimiter(GaugeLimiter):

    def _has_pillow_reported_recently(self):
        time_window = 15  # time window in minutes in which throttling should be applied
        time_before_window = datetime.now(tz=timezone.utc) - timedelta(minutes=time_window)
        return self.gauge.get_last_reported_time() > time_before_window

    def allow_usage(self):
        if not self.gauge_definition:
            # No throttling if config to throttle is not set
            return True
        return not (self._is_ideal_throttle_condition() and self._has_pillow_reported_recently())

    def _is_ideal_throttle_condition(self):
        """
        The ideal throttle conditions are -
        - If throttler is enabled in the config AND
        - If we have reported values from scopes AND
        - The follwing conditions are considered -
            - If both max_value and average_value are set on the Defintion model,
            then both should be breached in order to throttle.
            - If only max_value is defined, then only max_value would be observed.
            - If only average_value is set, then only average value would be observed.
        """
        if not self.gauge_definition.is_enabled:
            # if throttling is disabled, don't throttle
            return False

        max_observed_value = self.gauge.max()
        avg_observed_value = self.gauge.avg()

        if max_observed_value is None or avg_observed_value is None:
            # Don't throttle unless both observed values are set
            return False

        max_value = self.gauge_definition.max_value
        average_value = self.gauge_definition.average_value

        if max_value is not None and average_value is not None:
            return max_observed_value > max_value and avg_observed_value > average_value
        elif max_value is not None:
            return max_observed_value > max_value
        elif average_value is not None:
            return avg_observed_value > average_value
        return False
