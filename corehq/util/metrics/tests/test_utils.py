from datetime import timedelta

from django.test import SimpleTestCase
from testil import eq

from corehq.util.metrics import make_buckets_from_timedeltas, DAY_SCALE_TIME_BUCKETS, bucket_value
from corehq.util.test_utils import generate_cases


def test_make_buckets_from_timedeltas():
    buckets = [1, 10, 60, 10 * 60, 60 * 60, 12 * 60 * 60, 24 * 60 * 60]
    eq(make_buckets_from_timedeltas(
        timedelta(seconds=1),
        timedelta(seconds=10),
        timedelta(minutes=1),
        timedelta(minutes=10),
        timedelta(hours=1),
        timedelta(hours=12),
        timedelta(hours=24),
    ), buckets)
    eq(DAY_SCALE_TIME_BUCKETS, buckets)


class MetricsUtilsTest(SimpleTestCase):
    """Tests metrics utility functions"""

@generate_cases([
    (0, (1, 2, 5), '', 'lt_001'),
    (1, (1, 2, 5), '', 'lt_002'),
    (6, (1, 2, 5), '', 'over_005'),
    (101, (1, 2, 100), 's', 'over_100s'),
    (4, (1, 2, 5), 's', 'lt_005s'),
    (4, (1, 2, 5, 1000), 's', 'lt_0005s'),
    (6, (1, 2, 5, 1000, 43000), 's', 'lt_01000s'),
    (3000, (1, 2, 5, 1000), 's', 'over_1000s'),
], MetricsUtilsTest)
def test_bucket_value(self, value, buckets, unit, expected):
    self.assertEqual(bucket_value(value, buckets, unit), expected)
