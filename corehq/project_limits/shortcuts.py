import time

from corehq.project_limits.rate_limiter import RateDefinition
from corehq.util.metrics import bucket_value, metrics_counter
from corehq.util.timer import TimingContext

STANDARD_RATIO = RateDefinition(
    per_week=115,
    per_day=23,
    per_hour=3,
    per_minute=0.07,
    per_second=0.005,
).times(1 / 23)


def get_standard_ratio_rate_definition(events_per_day):
    return STANDARD_RATIO.times(events_per_day)


def delay_and_report_rate_limit(domain, max_wait, delay_rather_than_reject, datadog_metric, limiter):
    """
    Attempt to acquire permission from the rate limiter waiting up to :max_wait: seconds.

    When delay_rather_than_reject is False

        If it's acquired, report throttle_method:delay and duration:<bucketed duration>;
        otherwise report throttle_method:reject and duration:delayed_reject or quick_reject,
        depending on whether the rate limiter bothered to wait or could tell there was no chance.

    When delay_rather_than_reject is True

        If it's acquired, report throttle_method:delay and duration:<bucketed duration> (as before);
        otherwise report throttle_method:delay and duration:delay_rather_than_reject

    Returns whether the permission was eventually acquired (with no variation on delay_rather_than_reject).
    """
    with TimingContext() as timer:
        acquired = limiter.wait(domain, timeout=max_wait)
    if acquired:
        duration_tag = bucket_value(timer.duration, [.5, 1, 5, 10, 15], unit='s')
    elif delay_rather_than_reject:
        if timer.duration < max_wait:
            time.sleep(max_wait - timer.duration)
        duration_tag = 'delay_rather_than_reject'
    elif timer.duration < max_wait:
        duration_tag = 'quick_reject'
    else:
        duration_tag = 'delayed_reject'
    metrics_counter(datadog_metric, tags={
        'domain': domain,
        'duration': duration_tag,
        'throttle_method': "delay" if acquired or delay_rather_than_reject else "reject"
    })
    return acquired
