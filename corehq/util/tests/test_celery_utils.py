from datetime import timedelta, datetime

from celery.schedules import crontab
from freezegun import freeze_time
from nose.tools import assert_equal, assert_raises
from testil import eq

from corehq.util.celery_utils import deserialize_run_every_setting, run_periodic_task_again


def test_deserialize_run_every_setting():
    examples = [
        ({'crontab': {'minute': '*/30', 'hour': '0-5'}}, crontab(minute='*/30', hour='0-5')),
        ({'timedelta': {'minutes': 10}}, timedelta(minutes=10)),
        (30, 30),
    ]
    for input_value, expected_output_value in examples:
        assert_equal(deserialize_run_every_setting(input_value), expected_output_value)

    negative_examples = [
        # unacceptable function
        ({'nontab': {'args'}}, ValueError),
        # multiple functions
        ({'crontab': {'minute': '*/30', 'hour': '0-5'}, 'timedelta': {'minutes': 10}}, ValueError),
        # no function
        ({}, ValueError),
        # string
        ('30', ValueError),
        # bad params
        ({'crontab': {'foo': 'bar'}}, TypeError),
    ]
    for input_value, exception_type in negative_examples:
        with assert_raises(exception_type):
            deserialize_run_every_setting(input_value)


def test_run_periodic_task_again():
    def _test(run_every, last_run, duration, expected, now):
        with freeze_time(now):
            run_again = run_periodic_task_again(run_every, last_run, duration)
        eq(run_again, expected)

    now = datetime.utcnow()
    def nowfun(): return now
    all_hours = list(range(0, 24))
    all_hours_except_now = list(set(all_hours) - {now.hour})
    one_second = timedelta(seconds=1)
    one_second_ago = now - one_second
    run_every_minute = crontab(nowfun=nowfun)
    tests = [
        # (
        #   name,
        #   run_every,
        #   last_run,
        #   duration,
        #   expected
        # ),
        (
            'cron_already_triggered',
            run_every_minute,
            now - timedelta(minutes=2),
            one_second,
            False
        ),
        (
            'cron_enough_time',
            run_every_minute,
            one_second_ago,
            one_second,
            True
        ),
        (
            'cron_not_enough_time',
            run_every_minute,
            one_second_ago,
            timedelta(seconds=70),
            False
        ),
        (
            'cron_inside_window',
            crontab(hour=now.hour, nowfun=nowfun),
            one_second_ago,
            one_second,
            True
        ),
        (
            'cron_outside_window',
            crontab(hour=all_hours_except_now, nowfun=nowfun),
            one_second_ago,
            one_second,
            False
        ),

        (
            'repeat_enough_time',
            timedelta(minutes=1),
            now - timedelta(seconds=30),
            timedelta(seconds=20),
            True
        ),
        (
            'repeat_not_enough_time',
            timedelta(minutes=1),
            now - timedelta(seconds=30),
            timedelta(seconds=40),
            False
        ),
    ]

    for name, run_every, last_run, duration, expected in tests:
        yield lambda n: _test(run_every, last_run, duration, expected, now), name
