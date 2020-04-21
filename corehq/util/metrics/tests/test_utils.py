from datetime import timedelta

from django.test import SimpleTestCase
from testil import eq

from corehq.util.metrics import make_buckets_from_timedeltas, DAY_SCALE_TIME_BUCKETS, bucket_value
from corehq.util.metrics.utils import sanitize_url, get_url_group
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


@generate_cases([
    (
        '/a/uth-rhd/api/a26f2e21-5f24-48b6-b283-200a21f79bb6/20150922T034026.MP4',
        '/a/*/api/*/20150922T034026.MP4'
    ),
    ('/a/ben/modules-1/forms-2/uuid:abc123/', '/a/*/modules-*/forms-*/uuid:*/')
], MetricsUtilsTest)
def test_sanitize_url(self, url, sanitized):
    self.assertEqual(sanitize_url(url), sanitized)


@generate_cases([
    ('/', 'other'),
    ('/a/*/api', 'api'),
    ('/a/domain', 'other'),
    ('/1/2/3/4', 'other'),
    ('/a/*/cloudcare', 'cloudcare'),
], MetricsUtilsTest)
def test_url_group(self, url, group):
    self.assertEqual(get_url_group(url), group)
