from datetime import timedelta

from corehq.util.datadog.utils import make_bucket_from_timedeltas, DAY_SCALE_TIME_BUCKETS


def test_make_bucket_from_timedeltas():
    buckets = [1, 10, 60, 10 * 60, 60 * 60, 12 * 60 * 60, 24 * 60 * 60]
    assert make_bucket_from_timedeltas(
        timedelta(seconds=1),
        timedelta(seconds=10),
        timedelta(minutes=1),
        timedelta(minutes=10),
        timedelta(hours=1),
        timedelta(hours=12),
        timedelta(hours=24),
    ) == buckets
    assert DAY_SCALE_TIME_BUCKETS == buckets
