from __future__ import absolute_import
import calendar
import hashlib
import json
from corehq.messaging.scheduling.exceptions import InvalidMonthlyScheduleConfiguration
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast
from corehq.messaging.scheduling import util
from corehq.util.timezones.conversions import UserTime
from datetime import timedelta, datetime, date
from dimagi.utils.decorators.memoized import memoized
from django.db import models, transaction


class TimedSchedule(Schedule):
    REPEAT_INDEFINITELY = -1
    MONTHLY = -1

    ANY_DAY = -1
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

    schedule_length = models.IntegerField()
    total_iterations = models.IntegerField()
    start_offset = models.IntegerField(default=0)
    start_day_of_week = models.IntegerField(default=ANY_DAY)

    @property
    @memoized
    def memoized_schedule_revision(self):
        """
        The schedule revision is a hash of all information pertaining to
        scheduling. Information unrelated to scheduling, such as the content
        being sent at each event, is excluded. This is mainly used to determine
        when a TimedScheduleInstance should recalculate its schedule.
        """
        schedule_info = json.dumps([
            self.schedule_length,
            self.total_iterations,
            self.start_offset,
            self.start_day_of_week,
            [[e.day, e.time.strftime('%H:%M:%S')] for e in self.memoized_events],
        ])
        return hashlib.md5(schedule_info).hexdigest()

    @property
    @memoized
    def memoized_events(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the event set is not changing.
        """
        return list(self.timedevent_set.order_by('order'))

    def set_first_event_due_timestamp(self, instance, start_date=None):
        """
        If start_date is None, we set it automatically ensuring that
        self.next_event_due does not get set in the past for the first
        event.
        """
        if start_date:
            instance.start_date = start_date
        else:
            instance.start_date = instance.today_for_recipient

        self.set_next_event_due_timestamp(instance)

        if (
            self.schedule_length != self.MONTHLY and
            not start_date and
            instance.next_event_due < util.utcnow()
        ):
            if self.start_day_of_week == self.ANY_DAY:
                instance.start_date += timedelta(days=1)
                instance.next_event_due += timedelta(days=1)
            else:
                instance.start_date += timedelta(days=7)
                instance.next_event_due += timedelta(days=7)

    def get_start_date_with_start_offsets(self, instance):
        start_date_with_start_offsets = instance.start_date + timedelta(days=self.start_offset)

        if self.start_day_of_week != self.ANY_DAY:
            if self.start_day_of_week < self.MONDAY or self.start_day_of_week > self.SUNDAY:
                raise ValueError("Expected start_day_of_week to be between 0 and 6 for schedule %s" %
                    self.schedule_id)

            while start_date_with_start_offsets.weekday() != self.start_day_of_week:
                start_date_with_start_offsets += timedelta(days=1)

        return start_date_with_start_offsets

    def get_local_next_event_due_timestamp(self, instance):
        current_event = self.memoized_events[instance.current_event_num]

        days_since_start_date = (
            ((instance.schedule_iteration_num - 1) * self.schedule_length) + current_event.day
        )

        return datetime.combine(
            self.get_start_date_with_start_offsets(instance) + timedelta(days=days_since_start_date),
            current_event.time
        )

    def get_local_next_event_due_timestamp_for_monthly_schedule(self, instance):
        target_date = None
        start_date_with_offset = instance.start_date + timedelta(days=self.start_offset)

        while target_date is None:
            current_event = self.memoized_events[instance.current_event_num]

            if current_event.day < -28 or current_event.day == 0 or current_event.day > 31:
                # Negative days are days from the end of the month, with -1
                # being the last day of the month. We don't allow this going
                # past -28 since it's not very useful to do so, and imposing
                # this restriction lets us make the assumption that we can
                # always schedule a negative day.
                raise InvalidMonthlyScheduleConfiguration("Day must be between -28 and 31, and not be 0")

            year_offset = (instance.schedule_iteration_num - 1) / 12
            month_offset = (instance.schedule_iteration_num - 1) % 12

            year = start_date_with_offset.year + year_offset
            month = start_date_with_offset.month + month_offset

            days_in_month = calendar.monthrange(year, month)[1]
            if current_event.day > 0:
                if current_event.day > days_in_month:
                    # If the day refers to a date that is not possible to schedule
                    # (for example, February 30th), just move to the next month.
                    instance.schedule_iteration_num += 1
                    instance.current_event_num = 0
                    continue

                target_date = date(year, month, current_event.day)
            else:
                # It's a negative day, which counts back from the last day of the month
                target_date = date(year, month, days_in_month + current_event.day + 1)

        return datetime.combine(target_date, current_event.time)

    def set_next_event_due_timestamp(self, instance):
        if self.schedule_length == self.MONTHLY:
            user_timestamp = self.get_local_next_event_due_timestamp_for_monthly_schedule(instance)
        else:
            user_timestamp = self.get_local_next_event_due_timestamp(instance)

        instance.next_event_due = (
            UserTime(user_timestamp, instance.timezone)
            .server_time()
            .done()
            .replace(tzinfo=None)
        )

    def get_current_event_content(self, instance):
        current_event = self.memoized_events[instance.current_event_num]
        return current_event.memoized_content

    def move_to_next_event(self, instance):
        instance.current_event_num += 1
        if instance.current_event_num >= len(self.memoized_events):
            instance.schedule_iteration_num += 1
            instance.current_event_num = 0
        self.set_next_event_due_timestamp(instance)

        if (
            self.total_iterations != self.REPEAT_INDEFINITELY and
            instance.schedule_iteration_num > self.total_iterations
        ):
            instance.active = False

    def delete_related_events(self):
        for event in self.timedevent_set.all():
            event.content.delete()

        self.timedevent_set.all().delete()

    @classmethod
    def create_simple_daily_schedule(cls, domain, time, content, total_iterations=REPEAT_INDEFINITELY,
            start_offset=0, start_day_of_week=ANY_DAY, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_daily_schedule(time, content, total_iterations=total_iterations,
            start_offset=start_offset, start_day_of_week=start_day_of_week, extra_options=extra_options)
        return schedule

    def set_simple_daily_schedule(self, time, content, total_iterations=REPEAT_INDEFINITELY, start_offset=0,
            start_day_of_week=ANY_DAY, extra_options=None):
        with transaction.atomic():
            self.start_offset = start_offset
            self.start_day_of_week = start_day_of_week
            self.schedule_length = 1
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_DAILY
            self.set_extra_scheduling_options(extra_options)
            self.save()

            self.delete_related_events()

            if content.pk is None:
                content.save()

            event = TimedEvent(
                schedule=self,
                order=1,
                day=0,
                time=time
            )
            event.content = content
            event.save()

    def validate_day_of_week(self, day):
        if not isinstance(day, int) or day < 0 or day > 6:
            raise ValueError("Expected a value between 0 and 6")

    @classmethod
    def create_simple_weekly_schedule(cls, domain, time, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_weekly_schedule(time, content, days_of_week, start_day_of_week,
            total_iterations=total_iterations, extra_options=extra_options)
        return schedule

    def set_simple_weekly_schedule(self, time, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None):
        """
        Sets this TimedSchedule to be a simple weekly schedule where you can choose
        the days of the week on which to send.

        :param time: The time (datetime.time object) at which to send each day
        :param content: The content (corehq.messaging.scheduling.models.Content object) to send
        :days_of_week: A list of integers representing the days of the week on which to send, with
            0 being Monday and 6 being Sunday to match python's datetime.weekday() method
        :start_day_of_week: The day of the week which will be considered the first day of the week for
            scheduling purposes
        :param total_iterations: The total number of weeks to send for
        """
        self.validate_day_of_week(start_day_of_week)

        with transaction.atomic():
            self.start_day_of_week = start_day_of_week
            self.schedule_length = 7
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_WEEKLY
            self.start_offset = 0
            self.set_extra_scheduling_options(extra_options)
            self.save()

            self.delete_related_events()

            event_days = []
            for day in days_of_week:
                self.validate_day_of_week(day)
                event_days.append((day - start_day_of_week + 7) % 7)

            order = 1
            for day in sorted(event_days):
                event = TimedEvent(
                    schedule=self,
                    order=order,
                    day=day,
                    time=time
                )

                if order == 1:
                    if content.pk is None:
                        content.save()
                else:
                    # Create copies of the content on subsequent events
                    content.pk = None
                    content.save()

                event.content = content
                event.save()
                order += 1

    @classmethod
    def create_simple_monthly_schedule(cls, domain, time, days, content, total_iterations=REPEAT_INDEFINITELY,
            extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_monthly_schedule(time, days, content, total_iterations=total_iterations,
            extra_options=extra_options)
        return schedule

    def set_simple_monthly_schedule(self, time, days, content, total_iterations=REPEAT_INDEFINITELY,
            extra_options=None):
        with transaction.atomic():
            self.schedule_length = self.MONTHLY
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_MONTHLY
            self.start_offset = 0
            self.set_extra_scheduling_options(extra_options)
            self.save()

            self.delete_related_events()

            if content.pk is None:
                content.save()

            order = 1
            for day in days:
                event = TimedEvent(
                    schedule=self,
                    order=order,
                    day=day,
                    time=time
                )

                if order > 1:
                    content.pk = None
                    content.save()

                event.content = content
                event.save()
                order += 1


class TimedEvent(Event):
    schedule = models.ForeignKey('scheduling.TimedSchedule', on_delete=models.CASCADE)
    day = models.IntegerField()
    time = models.TimeField()


class ScheduledBroadcast(Broadcast):
    schedule = models.ForeignKey('scheduling.TimedSchedule', on_delete=models.CASCADE)
    start_date = models.DateField()
