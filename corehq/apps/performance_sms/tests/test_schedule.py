import uuid
import random
from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.performance_sms.dbaccessors import delete_all_configs
from corehq.apps.performance_sms.models import (DAILY, WEEKLY, MONTHLY, PerformanceConfiguration,
                                                DEFAULT_HOUR, DEFAULT_WEEK_DAY, DEFAULT_MONTH_DAY,
                                                ScheduleConfiguration)
from corehq.apps.performance_sms.schedule import get_message_configs_at_this_hour, get_daily_messages, \
    get_weekly_messages, get_monthly_messages


class TestSchedule(TestCase):
    domain = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        delete_all_configs()

    def test_daily_schedule(self):
        config = _make_performance_config(self.domain, DAILY, hour=4)
        try:
            as_of = _make_time(hours=4)
            configs_at_4_hours = get_message_configs_at_this_hour(as_of=as_of)
            self.assertEqual(1, len(configs_at_4_hours))
            self.assertEqual(config._id, configs_at_4_hours[0]._id)

            # check subfunctions
            self.assertEqual(1, len(get_daily_messages(as_of)))
            self.assertEqual(0, len(get_weekly_messages(as_of)))
            self.assertEqual(0, len(get_monthly_messages(as_of)))

            # any hour that's not 4am
            not_4 = random.choice(range(0, 4) + range(5, 24))
            self.assertEqual(0, len(get_daily_messages(_make_time(hours=not_4))))
        finally:
            config.delete()

    def test_weekly_schedule(self):
        config = _make_performance_config(self.domain, WEEKLY, day_of_week=4)
        try:
            as_of = _make_time(day_of_week=4)
            configs_on_4th_day = get_message_configs_at_this_hour(as_of=as_of)
            self.assertEqual(1, len(configs_on_4th_day))
            self.assertEqual(config._id, configs_on_4th_day[0]._id)

            # check subfunctions
            self.assertEqual(0, len(get_daily_messages(as_of)))
            self.assertEqual(1, len(get_weekly_messages(as_of)))
            self.assertEqual(0, len(get_monthly_messages(as_of)))

            # any weekday that's not 4th
            not_4 = random.choice(range(0, 4) + range(5, 7))
            self.assertEqual(0, len(get_weekly_messages(as_of=_make_time(day_of_week=not_4))))
        finally:
            config.delete()

    def test_monthly_schedule(self):
        # Todo, doesn't handle last-day-of-month
        config = _make_performance_config(self.domain, MONTHLY, hour=8, day_of_month=4)
        try:
            as_of = datetime(2015, 1, 4, 8)
            configs_on_4th_day = get_message_configs_at_this_hour(as_of=as_of)
            self.assertEqual(1, len(configs_on_4th_day))
            self.assertEqual(config._id, configs_on_4th_day[0]._id)

            # check subfunctions
            self.assertEqual(0, len(get_daily_messages(as_of)))
            self.assertEqual(0, len(get_weekly_messages(as_of)))
            self.assertEqual(1, len(get_monthly_messages(as_of)))

            # check wrong day
            wrong_day = as_of.replace(day=5)
            self.assertEqual(0, len(get_monthly_messages(as_of=wrong_day)))

            # check wrong hour
            wrong_hour = as_of.replace(hour=5)
            self.assertEqual(0, len(get_monthly_messages(as_of=wrong_hour)))
        finally:
            config.delete()


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


def _make_performance_config(domain, interval, hour=DEFAULT_HOUR, day_of_week=DEFAULT_WEEK_DAY,
                             day_of_month=DEFAULT_MONTH_DAY):
    config = PerformanceConfiguration(
        domain=domain,
        recipient_id=uuid.uuid4().hex,
        template='test',
        schedule=ScheduleConfiguration(
            interval=interval,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
        )
    )
    config.save()
    return config
