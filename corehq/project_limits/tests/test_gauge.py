from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from nose.tools import nottest

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import CASE_SQL
from corehq.project_limits.gauge import (
    Gauge,
    PillowLagGaugeLimiter,
    case_pillow_lag_gauge,
    get_pillow_throttle_definition,
)
from corehq.project_limits.models import PillowLagGaugeDefinition


class TestKafkaPillowGauge(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.feature_key = CASE_SQL
        cls.scopes = topics.get_all_kafka_partitons_for_topic(cls.feature_key)
        cls.case_gauge = case_pillow_lag_gauge

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


class TestPillowLagGaugeLimiter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scopes = ['topic-0', 'topic-1']
        cls.patcher = patch.object(topics, 'get_all_kafka_partitons_for_topic', return_value=cls.scopes)
        cls.patcher.start()

        cls.feature_key = CASE_SQL
        cls.gauge_obj = Gauge(CASE_SQL, topics.get_all_kafka_partitons_for_topic)

        cls.lag_limiter = PillowLagGaugeLimiter(cls.gauge_obj, get_pillow_throttle_definition)

        PillowLagGaugeDefinition.objects.all().delete()
        cls.gauge_defintion = PillowLagGaugeDefinition.objects.create(
            key=cls.feature_key,
            wait_for_seconds=5,
            max_value=10,
            average_value=8
        )

    def setUp(self):
        super().setUp()
        self._set_gauge_defintion(10, 8)

    @nottest
    def _set_gauge_defintion(self, max_value, average_value):
        self.gauge_defintion.max_value = max_value
        self.gauge_defintion.average_value = average_value
        self.gauge_defintion.save()

    def test_allow_usage_when_below_limits(self):
        self.gauge_obj.report('topic-0', 5)
        self.gauge_obj.report('topic-1', 7)

        self.assertTrue(self.lag_limiter.allow_usage())

    def test_allow_usage_when_limit_breach_on_max_only(self):
        self.gauge_obj.report('topic-0', 11)
        self.gauge_obj.report('topic-1', 5)

        self.assertTrue(self.lag_limiter.allow_usage())

    def test_allow_usage_when_limit_breach_on_avg_only(self):
        self.gauge_obj.report('topic-0', 9)
        self.gauge_obj.report('topic-1', 8)

        self.assertTrue(self.lag_limiter.allow_usage())

    def test_allow_usage_when_limit_breach_on_avg_and_max(self):
        self.gauge_obj.report('topic-0', 10)
        self.gauge_obj.report('topic-1', 15)

        self.assertFalse(self.lag_limiter.allow_usage())

    def test_allow_usage_with_average_not_set(self):
        self._set_gauge_defintion(max_value=15, average_value=None)

        self.gauge_obj.report('topic-0', 14)
        self.gauge_obj.report('topic-1', 13)

        self.assertTrue(self.lag_limiter.allow_usage())

        self.gauge_obj.get_values.clear(self.gauge_obj)

        # Should not allow since max value is breached
        self.gauge_obj.report('topic-0', 16)
        self.assertFalse(self.lag_limiter.allow_usage())

    def test_allow_usage_with_max_not_set(self):
        self._set_gauge_defintion(max_value=None, average_value=10)

        self.gauge_obj.report('topic-0', 15)
        self.gauge_obj.report('topic-1', 2)

        self.assertTrue(self.lag_limiter.allow_usage())

        self.gauge_obj.get_values.clear(self.gauge_obj)
        self.gauge_obj.report('topic-1', 8)

        # Should not allow since average value is breached
        self.assertFalse(self.lag_limiter.allow_usage())

    def test_allow_usage_with_single_partition(self):
        self.gauge_obj.report('topic-0', 9)

        self.assertTrue(self.lag_limiter.allow_usage())

    def test_allow_usage_with_no_reported_values(self):
        self.assertTrue(self.lag_limiter.allow_usage())

    def tearDown(self):
        # cache cleanup
        for scope in self.scopes:
            cache.delete(self.gauge_obj._tracked_event_cache_key(scope))
        self.gauge_obj.get_values.clear(self.gauge_obj)
        return super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        return super().tearDownClass()
