from unittest.mock import patch
from django.core.cache import cache
from nose.tools import nottest
from corehq.apps.change_feed.topics import CASE_SQL
from django.test import SimpleTestCase
from corehq.apps.change_feed.topics import get_all_kafka_partitons_for_topic
from corehq.project_limits.gauge import Gauge


class TestGauge(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.topic = CASE_SQL
        cls.scopes = get_all_kafka_partitons_for_topic(cls.topic)
        cls.case_gauge = Gauge(scopes=cls.scopes, topic=cls.topic)
        return super().setUpClass()

    @nottest
    def _report_usage_for_multiple_partitions(self, gauge, partitions, lag_values):
        for partition, lag in zip(partitions, lag_values):
            gauge.report(partition, lag)
            self.addCleanup(cache.delete, gauge._get_lag_cache_key(partition))
        self.addCleanup(cache.delete, gauge._get_last_reported_cache_key())

    def test_report_usage(self):
        kafka_partition = next(iter(self.scopes))
        pillow_lag = 60

        self.case_gauge.report(kafka_partition, pillow_lag)

        cache_key = self.case_gauge._get_lag_cache_key(kafka_partition)
        self.addCleanup(cache.delete, cache_key)
        saved_lag = cache.get(cache_key)
        self.assertEqual(saved_lag, pillow_lag)
        self.assertIsNotNone(self.case_gauge.get_last_reported_time())

    def test_get_values_for_single_partition(self):
        lag_before_populating = self.case_gauge.get_values()
        self.assertEqual(lag_before_populating, [])

        partition = next(iter(self.scopes))
        self.case_gauge.report(partition, 10)
        self.addCleanup(cache.delete, partition)

        self.assertEqual(self.case_gauge.get_values(), [10])

    @patch('corehq.project_limits.gauge.get_all_kafka_partitons_for_topic')
    def test_get_values_for_multiple_partitons(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_before_populating = self.case_gauge.get_values()
        self.assertEqual(lag_before_populating, [])

        lag_in_partitions = [10, 20, 30]
        case_gauge_with_multiple_partitions = Gauge(scopes=mocked_partitions, topic=self.topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.get_values(), lag_in_partitions)

    @patch('corehq.project_limits.gauge.get_all_kafka_partitons_for_topic')
    def test_max(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_in_partitions = [10, 20, 30]
        case_gauge_with_multiple_partitions = Gauge(scopes=mocked_partitions, topic=self.topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.max(), 30)

    @patch('corehq.project_limits.gauge.get_all_kafka_partitons_for_topic')
    def test_avg(self, mock_get_all_kafka_partitons_for_topic):
        mocked_partitions = ['topic-0', 'topic-1', 'topic-2']
        mock_get_all_kafka_partitons_for_topic.return_value = mocked_partitions

        lag_in_partitions = [15, 15, 30]
        case_gauge_with_multiple_partitions = Gauge(scopes=mocked_partitions, topic=self.topic)

        self._report_usage_for_multiple_partitions(
            case_gauge_with_multiple_partitions, mocked_partitions, lag_in_partitions
        )

        self.assertEqual(case_gauge_with_multiple_partitions.avg(), 20)
