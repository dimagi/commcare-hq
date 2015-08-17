import uuid
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
            as_of = datetime(2015, 1, 1, 4)
            configs_at_4_hours = get_message_configs_at_this_hour(as_of=as_of)
            self.assertEqual(1, len(configs_at_4_hours))
            self.assertEqual(config._id, configs_at_4_hours[0]._id)

            # check subfunctions
            self.assertEqual(1, len(get_daily_messages(as_of)))
            self.assertEqual(0, len(get_weekly_messages(as_of)))
            self.assertEqual(0, len(get_monthly_messages(as_of)))

            # test wrong hour
            wrong_hour = as_of.replace(hour=5)
            self.assertEqual(0, len(get_daily_messages(wrong_hour)))

            # test different day is fine
            new_day = as_of + timedelta(days=5)
            self.assertEqual(1, len(get_daily_messages(new_day)))
        finally:
            config.delete()

    def test_weekly_schedule(self):
        config = _make_performance_config(self.domain, WEEKLY, day_of_week=4, hour=8)
        try:
            as_of = datetime(2015, 8, 14, 8)  # happens to be a friday (weekday 4)
            configs_on_4th_day = get_message_configs_at_this_hour(as_of=as_of)
            self.assertEqual(1, len(configs_on_4th_day))
            self.assertEqual(config._id, configs_on_4th_day[0]._id)

            # check subfunctions
            self.assertEqual(0, len(get_daily_messages(as_of)))
            self.assertEqual(1, len(get_weekly_messages(as_of)))
            self.assertEqual(0, len(get_monthly_messages(as_of)))

            # any weekday that's not 4th
            wrong_day = as_of.replace(day=15)
            self.assertEqual(0, len(get_weekly_messages(wrong_day)))

            # wrong hour
            wrong_hour = as_of.replace(hour=7)
            self.assertEqual(0, len(get_weekly_messages(wrong_hour)))

            # one week later should be ok
            next_week = as_of + timedelta(days=7)
            self.assertEqual(1, len(get_weekly_messages(next_week)))

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

            # next month ok
            next_month = as_of.replace(month=2)
            self.assertEqual(1, len(get_monthly_messages(as_of=next_month)))
        finally:
            config.delete()


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
