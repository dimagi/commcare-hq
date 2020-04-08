from datetime import timedelta


def make_buckets_from_timedeltas(*timedeltas):
    return [td.total_seconds() for td in timedeltas]


DAY_SCALE_TIME_BUCKETS = make_buckets_from_timedeltas(
    timedelta(seconds=1),
    timedelta(seconds=10),
    timedelta(minutes=1),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=12),
    timedelta(hours=24),
)
