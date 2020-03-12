from typing import Dict, Tuple

from django.test import SimpleTestCase
from django.utils.functional import SimpleLazyObject

from corehq.util.metrics import DatadogMetrics, PrometheusMetrics
from corehq.util.metrics.metrics import (
    DelegatedMetrics,
    HqCounter,
    HqGauge,
    HqHistogram,
)
from corehq.util.metrics.tests.utils import patch_datadog
from prometheus_client.samples import Sample
from prometheus_client.utils import INF
from testil import eq


class _TestMetrics(SimpleTestCase):
    provider_class = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.provider_class()

    def test_counter(self):
        counter = self.provider.counter('commcare.test.counter', 'Description', tag_names=['t1', 't2'])
        counter.tag(t1='a', t2='b').inc()
        counter.tag(t1='c', t2='b').inc(2)
        counter.tag(t1='c', t2='b').inc()
        self.assertCounterMetric(counter, {
            (('t1', 'a'), ('t2', 'b')): 1,
            (('t1', 'c'), ('t2', 'b')): 3,
        })

    def test_gauge(self):
        gauge = self.provider.gauge('commcare.test.gauge', 'Description', tag_names=['t1', 't2'])
        gauge.tag(t1='a', t2='b').set(4.2)
        gauge.tag(t1='c', t2='b').set(2)
        gauge.tag(t1='c', t2='b').set(5)
        self.assertGaugeMetric(gauge, {
            (('t1', 'a'), ('t2', 'b')): 4.2,
            (('t1', 'c'), ('t2', 'b')): 5,
        })

    def assertCounterMetric(self, metric: HqCounter, expected: Dict[Tuple[Tuple[str, str], ...], float]):
        """
        :param metric: metric class
        :param expected: dict mapping tag tuples to metric values
        """
        raise NotImplementedError

    def assertGaugeMetric(self, metric: HqGauge, expected: Dict[Tuple[Tuple[str, str], ...], float]):
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
        histogram = self.provider.histogram(
            'commcare.test.histogram', 'Description', 'duration',
            buckets=[1, 2, 3], bucket_unit='ms', tag_names=['t1', 't2']
        )
        tagged_1 = histogram.tag(t1='a', t2='b')
        tagged_1.observe(0.2)
        tagged_1.observe(0.7)
        tagged_1.observe(2.5)

        tagged_2 = histogram.tag(t1='c', t2='b')
        tagged_2.observe(2)
        tagged_2.observe(5)
        self.assertHistogramMetric(histogram, {
            (('t1', 'a'), ('t2', 'b')): {1: 2, 3: 1},
            (('t1', 'c'), ('t2', 'b')): {3: 1, INF: 1}
        })

    def assertCounterMetric(self, metric, expected):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric.name})
        actual = {
            key[1]: sum(val) for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected)

    def assertGaugeMetric(self, metric, expected):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric.name})
        actual = {
            key[1]: val[-1] for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected)

    def assertHistogramMetric(self, metric, expected):
        self.assertEqual({key[0] for key in self.recorded_metrics}, {metric.name})
        expected_samples = {}
        for tags, buckets in expected.items():
            for bucket, val in buckets.items():
                prefix = 'lt'
                if bucket == INF:
                    bucket = metric._buckets[-1]
                    prefix = 'over'
                bucket_tag = (metric._bucket_tag, f'{prefix}_{bucket:03d}{metric._bucket_unit}')
                expected_samples[tuple(sorted(tags + (bucket_tag,)))] = val

        actual = {
            key[1]: sum(val) for key, val in self.recorded_metrics.items()
        }
        self.assertDictEqual(actual, expected_samples)


class TestPrometheusMetrics(_TestMetrics):
    provider_class = PrometheusMetrics

    def test_histogram(self):
        histogram = self.provider.histogram(
            'commcare.test.histogram', 'Description', 'duration',
            buckets=[1, 2, 3], bucket_unit='ms', tag_names=['t1', 't2']
        )
        tagged_1 = histogram.tag(t1='a', t2='b')
        tagged_1.observe(0.2)
        tagged_1.observe(0.7)
        tagged_1.observe(2.5)

        tagged_2 = histogram.tag(t1='c', t2='b')
        tagged_2.observe(2)
        tagged_2.observe(5)
        self.assertHistogramMetric(histogram, {
            (('t1', 'a'), ('t2', 'b')): {1: 2, 3: 1},
            (('t1', 'c'), ('t2', 'b')): {2: 1, INF: 1}
        })

    def _samples_to_dics(self, samples, filter_name=None):
        """Convert a Sample tuple into a dict((name, (labels tuple)) -> value)"""
        return {
            tuple(sample.labels.items()): sample.value
            for sample in samples
            if not filter_name or sample.name == filter_name
        }

    def assertGaugeMetric(self, metric, expected):
        [collected] = metric._delegate.collect()
        actual = self._samples_to_dics(collected.samples)
        self.assertDictEqual(actual, expected)

    def assertCounterMetric(self, metric, expected):
        total_name = f'{metric.name}_total'
        [collected] = metric._delegate.collect()
        actual = self._samples_to_dics(collected.samples, total_name)
        self.assertDictEqual(actual, expected)

    def assertHistogramMetric(self, metric, expected):
        # Note that Prometheus histograms are cumulative so we must sum up the successive bucket values
        # https://en.wikipedia.org/wiki/Histogram#Cumulative_histogram
        [collected] = metric._delegate.collect()

        sample_name = f'{metric.name}_bucket'
        expected_samples = []
        for key, value in expected.items():
            cumulative_value = 0
            for bucket in metric._buckets:
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


def test_delegate_lazy():
    metrics = DelegatedMetrics([DatadogMetrics(), PrometheusMetrics()])

    def _check(metric):
        assert isinstance(metric, SimpleLazyObject), ''

    test_cases = [
        metrics.counter('commcare.name.1', ''),
        metrics.gauge('commcare.name.2', ''),
        metrics.histogram('commcare.name.3', '', 'duration'),
    ]
    for metric in test_cases:
        yield _check, metric


def test_lazy_recording():
    metrics = DelegatedMetrics([DatadogMetrics(), PrometheusMetrics()])

    def _check(metric, method_name):
        with patch_datadog() as stats:
            getattr(metric, method_name)(1)

        dd_metric, prom_metric = metric._delegates
        [collected] = prom_metric._delegate.collect()

        eq(len(stats), 1, stats)
        eq(len(collected.samples) >= 1, True, collected.samples)

    test_cases = [
        (metrics.counter('commcare.name.1', ''), 'inc'),
        (metrics.gauge('commcare.name.2', ''), 'set'),
        (metrics.histogram('commcare.name.3', '', 'duration'), 'observe'),
    ]
    for metric, method_name in test_cases:
        yield _check, metric, method_name
