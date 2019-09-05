from datetime import timedelta

from celery.schedules import crontab
from nose.tools import assert_equal, assert_raises

from corehq.util.celery_utils import deserialize_run_every_setting


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
