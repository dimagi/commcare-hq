from unittest.mock import patch
from django.core.cache import cache
from nose.tools import nottest
from corehq.apps.change_feed.topics import CASE_SQL
from django.test import SimpleTestCase
from corehq.apps.change_feed import topics
from corehq.project_limits.gauge import Gauge, case_pillow_lag_gauge


class TestKafkaPillowGauge(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.feature_key = CASE_SQL
        cls.scopes = topics.get_all_kafka_partitons_for_topic(cls.feature_key)
        cls.case_gauge = case_pillow_lag_gauge
        return super().setUpClass()

    @nottest
    def _report_usage_for_multiple_partitions(self, gauge, partitions, lag_values):
        for partition, lag in zip(partitions, lag_values):
            gauge.report(partition, lag)
            self.addCleanup(cache.delete, gauge._tracked_event_cache_key(partition))
        self.addCleanup(cache.delete, gauge._last_reported_timestamp_key)

    def test_report_usage(self):
        kafka_partition = next(iter(self.scopes))
        pillow_lag = 60

        self.case_gauge.report(kafka_partition, pillow_lag)

        cache_key = self.case_gauge._tracked_event_cache_key(kafka_partition)
        self.addCleanup(cache.delete, cache_key)
        saved_lag = cache.get(cache_key)
        self.assertEqual(saved_lag, pillow_lag)
        self.assertIsNotNone(self.case_gauge._last_reported_timestamp_key)

    def test_get_values_for_single_partition(self):
        lag_before_populating = self.case_gauge.get_values()
        self.assertEqual(lag_before_populating, [])
        self.case_gauge.get_values.clear(self.case_gauge)

        partition = next(iter(self.scopes))
        self.case_gauge.report(partition, 10)
        self.addCleanup(cache.delete, partition)
        self.addCleanup(self.case_gauge.get_values.clear, self.case_gauge)

        self.assertEqual(self.case_gauge.get_values(), [10])

    @patch.object(topics, 'get_all_kafka_partitons_for_topic')
    def test_get_values_for_multiple_partitons(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_before_populating = self.case_gauge.get_values()
        self.case_gauge.get_values.clear(self.case_gauge)

        self.assertEqual(lag_before_populating, [])

        lag_in_partitions = [10, 20, 30]
        case_gauge_with_multiple_partitions = Gauge(CASE_SQL, topics.get_all_kafka_partitons_for_topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.get_values(), lag_in_partitions)
        self.addCleanup(self.case_gauge.get_values.clear, self.case_gauge)

    @patch.object(topics, 'get_all_kafka_partitons_for_topic')
    def test_max(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_in_partitions = [10, 20, 30]
        case_gauge_with_multiple_partitions = Gauge(CASE_SQL, topics.get_all_kafka_partitons_for_topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.max(), 30)
        self.addCleanup(self.case_gauge.get_values.clear, self.case_gauge)

    @patch.object(topics, 'get_all_kafka_partitons_for_topic')
    def test_avg(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_in_partitions = [15, 15, 30]
        case_gauge_with_multiple_partitions = Gauge(CASE_SQL, topics.get_all_kafka_partitons_for_topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.avg(), 20)
        self.addCleanup(self.case_gauge.get_values.clear, self.case_gauge)
