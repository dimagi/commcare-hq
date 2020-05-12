from contextlib import contextmanager
from datetime import date

from nose.tools import assert_false, assert_true

from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from corehq.motech.dhis2.models import DataSetMap

DOMAIN = 'test-domain'


def test_send_monthly_yes():
    with monthly_datasetmap() as monthly_day_2:
        send_date = date(2020, 5, 2)
        assert_true(monthly_day_2.should_send_on_date(send_date))


def test_send_monthly_wrong_day():
    with monthly_datasetmap() as monthly_day_2:
        send_date = date(2020, 5, 3)
        assert_false(monthly_day_2.should_send_on_date(send_date))


def test_send_quarterly_yes():
    with quarterly_datasetmap() as quarterly_day_2:
        send_date = date(2020, 4, 2)
        assert_true(quarterly_day_2.should_send_on_date(send_date))


def test_send_quarterly_wrong_day():
    with quarterly_datasetmap() as quarterly_day_2:
        send_date = date(2020, 4, 3)
        assert_false(quarterly_day_2.should_send_on_date(send_date))


def test_send_quarterly_wrong_month():
    with quarterly_datasetmap() as quarterly_day_2:
        send_date = date(2020, 5, 2)
        assert_false(quarterly_day_2.should_send_on_date(send_date))


def test_send_weekly_yes():
    with weekly_datasetmap() as weekly_day_2:
        send_date = date(2020, 5, 5)  # Tuesday ("2020-W19-2")
        assert_true(weekly_day_2.should_send_on_date(send_date))


def test_send_weekly_wrong_day():
    with weekly_datasetmap() as weekly_day_2:
        send_date = date(2020, 5, 2)  # Saturday ("2020-W18-6")
        assert_false(weekly_day_2.should_send_on_date(send_date))


@contextmanager
def weekly_datasetmap():
    try:
        yield DataSetMap(
            domain=DOMAIN,
            frequency=SEND_FREQUENCY_WEEKLY,
            day_to_send=2,
        )
    finally:
        pass


@contextmanager
def monthly_datasetmap():
    try:
        yield DataSetMap(
            domain=DOMAIN,
            frequency=SEND_FREQUENCY_MONTHLY,
            day_to_send=2,
        )
    finally:
        pass


@contextmanager
def quarterly_datasetmap():
    try:
        yield DataSetMap(
            domain=DOMAIN,
            frequency=SEND_FREQUENCY_QUARTERLY,
            day_to_send=2,
        )
    finally:
        pass
