from datetime import datetime

from django.core.cache import cache

from corehq.apps.change_feed.topics import (
    CASE_SQL,
    get_all_kafka_partitons_for_topic,
)


class Gauge:
    """
    A util class for reporting gauge metrics for kafka lag.
    :param scopes: (list) is a list of kafka partitions like ['case-sql-1', 'case-sql-2',...]
    :param topic: (str) is the kafka topic name like `case-sql`
    :param timeout: (int) is the number of seconds to cache the lag value
    TODO: Think about caching
    """
    def __init__(self, topic, scopes=None, timeout=8 * 60):
        if not scopes:
            scopes = get_all_kafka_partitons_for_topic(topic)
            if not scopes:
                raise Exception(f"No kafka partitions found for topic {topic}")
        self.scopes = scopes
        self.timeout = timeout
        self.topic = topic

    def report(self, kafka_partition, lag):
        """
        :kafka_partition: str like `topic-1`, `case-sql-1` etc
        :lag: int time in seconds
        Save the lag for the kafka partition and also updates last reported time.
        """
        assert kafka_partition in self.scopes, f"{kafka_partition} not a known topic {self.scopes}"
        cache.set(self._get_lag_cache_key(kafka_partition), lag, timeout=self.timeout)
        cache.set(self._get_last_reported_cache_key(), datetime.now(), timeout=self.timeout)

    def get_values(self):
        """
        returns a list of lag for all kafka partitions for a given topic
        """
        all_cache_keys = [self._get_lag_cache_key(partition) for partition in self.scopes]
        delay_by_partition = cache.get_many(all_cache_keys)
        return list(delay_by_partition.values())

    def _get_lag_cache_key(self, kafka_partition):
        return f'{kafka_partition}-lag'

    def _get_last_reported_cache_key(self):
        return f'{self.topic}-last-reported'

    def get_last_reported_time(self):
        "returns the last time when the lag was reported"
        return cache.get(self._get_last_reported_cache_key(), datetime.now())

    def max(self):
        """
        return max lag for a given topic
        """
        return int(max(self.get_values()))

    def avg(self):
        """
        return average lag for a given topic
        """
        all_values = self.get_values()
        return int(sum(all_values) / len(all_values))


case_gauge = Gauge(CASE_SQL)
