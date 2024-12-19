from typing import Dict, Tuple

from django.test import SimpleTestCase
from django.utils.functional import classproperty

from corehq.util.metrics.datadog import DatadogMetrics
from corehq.util.metrics.prometheus import PrometheusMetrics
from corehq.util.metrics.tests.utils import patch_datadog
from prometheus_client.samples import Sample
from prometheus_client.utils import INF


class _TestMetrics(SimpleTestCase):
    provider_class = None

    @classproperty
    def __test__(cls):
        return cls.provider_class is not None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.provider_class()

    def test_counter(self):
        self.provider.counter('commcare.test.counter', tags={'t1': 'a', 't2': 'b'})
        self.provider.counter('commcare.test.counter', 2, tags={'t1': 'c', 't2': 'b'})
        self.provider.counter('commcare.test.counter', tags={'t1': 'c', 't2': 'b'})
        self.assertCounterMetric('commcare.test.counter', {
            (('t1', 'a'), ('t2', 'b')): 1,
            (('t1', 'c'), ('t2', 'b')): 3,
        })

    def test_gauge(self):
        self.provider.gauge('commcare.test.gauge', 4.2, tags={'t1': 'a', 't2': 'b'})
        self.provider.gauge('commcare.test.gauge', 2, tags={'t1': 'c', 't2': 'b'})
        self.provider.gauge('commcare.test.gauge', 5, tags={'t1': 'c', 't2': 'b'})
        self.assertGaugeMetric('commcare.test.gauge', {
            (('t1', 'a'), ('t2', 'b')): 4.2,
            (('t1', 'c'), ('t2', 'b')): 5,
        })

    def assertCounterMetric(self, metric: str, expected: Dict[Tuple[Tuple[str, str], ...], float]):
        """
        :param metric: metric class
        :param expected: dict mapping tag tuples to metric values
        """
        raise NotImplementedError

    def assertGaugeMetric(self, metric: str, expected: Dict[Tuple[Tuple[str, str], ...], float]):
        """
        :param metric: metric class
        :param expected: dict mapping tag tuples to metric values
        """
        raise NotImplementedError


class TestDatadogMetrics(_TestMetrics):
    provider_class = DatadogMetrics

    def setUp(self) -> None:
        super().setUp()
        self.patch = patch_datadog()
        self.recorded_metrics = self.patch.__enter__()

    def tearDown(self) -> None:
        self.patch.__exit__(None, None, None)
        super().tearDown()

    def test_histogram(self):
        for value in (0.2, 0.7, 2.5):
            self.provider.histogram(
                'commcare.test.histogram', value, 'duration',
                buckets=[1, 2, 3], bucket_unit='ms', tags={'t1': 'a', 't2': 'b'}
            )
        for value in (2, 5):
            self.provider.histogram(
                'commcare.test.histogram', value, 'duration',
                buckets=[1, 2, 3], bucket_unit='ms', tags={'t1': 'c', 't2': 'b'}
            )
        self.assertHistogramMetric('commcare.test.histogram', {
            (('t1', 'a'), ('t2', 'b')): {1: 2, 3: 1},
            (('t1', 'c'), ('t2', 'b')): {3: 1, INF: 1}
        }, 'duration', [1, 2, 3], 'ms')

    def assertCounterMetric(self, metric_name, expected):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric_name})
        actual = {
            key[1]: sum(val) for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected)

    def assertGaugeMetric(self, metric_name, expected):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric_name})
        actual = {
            key[1]: val[-1] for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected)

    def assertHistogramMetric(self, metric_name, expected, bucket_tag, buckets, bucket_unit):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric_name})
        expected_samples = {}
        for tags, expected_buckets in expected.items():
            for bucket, val in expected_buckets.items():
                prefix = 'lt'
                if bucket == INF:
                    bucket = buckets[-1]
                    prefix = 'over'
                dd_bucket_tag = (bucket_tag, f'{prefix}_{bucket:03d}{bucket_unit}')
                expected_samples[tuple(sorted(tags + (dd_bucket_tag,)))] = val

        actual = {
            key[1]: sum(val) for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected_samples)


class TestPrometheusMetrics(_TestMetrics):
    provider_class = PrometheusMetrics

    def test_histogram(self):
        for value in (0.2, 0.7, 2.5):
            self.provider.histogram(
                'commcare_test_histogram', value, 'duration',
                buckets=[1, 2, 3], bucket_unit='ms', tags={'t1': 'a', 't2': 'b'}
            )
        for value in (2, 5):
            self.provider.histogram(
                'commcare_test_histogram', value, 'duration',
                buckets=[1, 2, 3], bucket_unit='ms', tags={'t1': 'c', 't2': 'b'}
            )
        self.assertHistogramMetric('commcare_test_histogram', {
            (('t1', 'a'), ('t2', 'b')): {1: 2, 3: 1},
            (('t1', 'c'), ('t2', 'b')): {2: 1, INF: 1}
        }, [1, 2, 3])

    def _samples_to_dics(self, samples, filter_name=None):
        """Convert a Sample tuple into a dict((name, (labels tuple)) -> value)"""
        return {
            tuple(sorted(sample.labels.items())): sample.value
            for sample in samples
            if not filter_name or sample.name == filter_name
        }

    def assertGaugeMetric(self, metric_name, expected):
        metric_name = metric_name.replace('.', '_')
        metric = self.provider._metrics[metric_name]
        [collected] = metric.collect()
        actual = self._samples_to_dics(collected.samples)
        self.assertDictEqual(actual, expected)

    def assertCounterMetric(self, metric_name, expected):
        metric_name = metric_name.replace('.', '_')
        metric = self.provider._metrics[metric_name]
        total_name = f'{metric_name}_total'
        [collected] = metric.collect()
        actual = self._samples_to_dics(collected.samples, total_name)
        self.assertDictEqual(actual, expected)

    def assertHistogramMetric(self, metric_name, expected, buckets):
        # Note that Prometheus histograms are cumulative so we must sum up the successive bucket values
        # https://en.wikipedia.org/wiki/Histogram#Cumulative_histogram
        metric = self.provider._metrics[metric_name]
        [collected] = metric.collect()

        sample_name = f'{metric_name}_bucket'
        expected_samples = []
        for key, value in expected.items():
            cumulative_value = 0
            for bucket in buckets:
                val = value.get(bucket, 0)
                cumulative_value += val
                labels = dict(key + (('le', str(float(bucket))),))
                expected_samples.append(Sample(sample_name, labels, float(cumulative_value), None, None))

            labels = dict(key + (('le', '+Inf'),))
            cumulative_value += value.get(INF, 0)
            expected_samples.append(Sample(sample_name, labels, float(cumulative_value), None, None))

        actual = [
            s for s in collected.samples
            if s.name.endswith('bucket')
        ]
        self.assertListEqual(actual, expected_samples)
