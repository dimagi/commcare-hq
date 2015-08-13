import uuid
import random
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.performance_sms.models import (DAILY, WEEKLY, MONTHLY, PerformanceConfiguration,
                                                DEFAULT_HOUR, DEFAULT_WEEK_DAY, DEFAULT_MONTH_DAY)
from corehq.apps.performance_sms.utils import get_message_configs_at_this_hour


class TestSchedule(TestCase):
    domain = uuid.uuid4().hex

    def test_daily_schedule(self):
        config = _make_daily_performance_config(self.domain, hour=4)

        configs_at_4_hours = get_message_configs_at_this_hour(as_of=_make_time(hours=4))
        self.assertTrue(config._id in [c._id for c in configs_at_4_hours])

        not_4 = random.choice(range(0, 4) + range(5, 24))
        configs_not_at_4_hours = get_message_configs_at_this_hour(as_of=_make_time(hours=not_4))
        self.assertFalse(config._id in [c._id for c in configs_not_at_4_hours])

    def test_weekly_schedule(self):
        config = _make_weekly_performance_config(self.domain, day_of_week=4)

        configs_on_4th_day = get_message_configs_at_this_hour(as_of=_make_time(day_of_week=4))
        self.assertTrue(config._id in [c._id for c in configs_on_4th_day])

        not_4 = random.choice(range(0, 4) + range(5, 8))
        configs_not_on_4thday = get_message_configs_at_this_hour(as_of=_make_time(hours=not_4))
        self.assertFalse(config._id in [c._id for c in configs_not_on_4thday])

    def test_monthly_schedule(self):
        # Todo, doesn't handle last-day-of-month
        config = _make_monthly_performance_config(self.domain, day_of_month=4)

        configs_on_4th_day = get_message_configs_at_this_hour(as_of=_make_time(day_of_month=4))
        self.assertTrue(config._id in [c._id for c in configs_on_4th_day])

        not_4 = random.choice(range(0, 4) + range(5, 29))
        configs_not_on_4thday = get_message_configs_at_this_hour(as_of=_make_time(hours=not_4))
        self.assertFalse(config._id in [c._id for c in configs_not_on_4thday])


def _make_time(hours=None, day_of_week=None, day_of_month=None):
    if hours:
        return datetime(2013, random.choice(range(1, 13)), random.choice(range(1, 29)), hours)

    if day_of_week:
        base_date = datetime(2013, random.choice(range(1, 13)), 1)
        while base_date.weekday() != day_of_week:
            base_date = base_date + timedelta(days=1)
        return base_date

    if day_of_month:
        return datetime(2013, random.choice(range(1, 13)), day_of_month)


def _make_daily_performance_config(domain, hour="0"):
    config = PerformanceConfiguration(
        domain=domain,
        recipient_id=uuid.uuid4().hex,
        template='test',
        interval=DAILY,
        hour=hour,
        day_of_week=DEFAULT_WEEK_DAY,
        day_of_month=DEFAULT_MONTH_DAY,
    )
    config.save()
    return config


def _make_weekly_performance_config(domain, day_of_week="1"):
    config = PerformanceConfiguration(
        domain=domain,
        recipient_id=uuid.uuid4().hex,
        template='test',
        interval=WEEKLY,
        hour=DEFAULT_HOUR,
        day_of_week=day_of_week,
        day_of_month=DEFAULT_MONTH_DAY,
    )
    config.save()
    return config


def _make_monthly_performance_config(domain, day_of_month="1"):
    config = PerformanceConfiguration(
        domain=domain,
        recipient_id=uuid.uuid4().hex,
        template='test',
        interval=MONTHLY,
        hour=DEFAULT_HOUR,
        day_of_week=DEFAULT_WEEK_DAY,
        day_of_month=day_of_month,
    )
    config.save()
    return config
