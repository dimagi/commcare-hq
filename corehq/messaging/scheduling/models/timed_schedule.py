from __future__ import absolute_import
import calendar
import hashlib
import json
import random
import re
from corehq.messaging.scheduling.exceptions import InvalidMonthlyScheduleConfiguration
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast
from corehq.messaging.scheduling import util
from corehq.util.timezones.conversions import UserTime
from datetime import timedelta, datetime, date, time
from dateutil.parser import parse
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

    EVENT_SPECIFIC_TIME = 'SPECIFIC_TIME'
    EVENT_RANDOM_TIME = 'RANDOM_TIME'
    EVENT_CASE_PROPERTY_TIME = 'CASE_PROPERTY_TIME'

    schedule_length = models.IntegerField()
    total_iterations = models.IntegerField()
    start_offset = models.IntegerField(default=0)
    start_day_of_week = models.IntegerField(default=ANY_DAY)
    event_type = models.CharField(max_length=50, default=EVENT_SPECIFIC_TIME)

    def get_schedule_revision(self, case=None):
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
            [e.get_scheduling_info(case=case) for e in self.memoized_events],
        ])
        return hashlib.md5(schedule_info).hexdigest()

    @property
    @memoized
    def memoized_events(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the event set is not changing.
        """
        return list(self.event_set.order_by('order'))

    @property
    def event_set(self):
        if self.event_type == self.EVENT_SPECIFIC_TIME:
            return self.timedevent_set
        elif self.event_type == self.EVENT_RANDOM_TIME:
            return self.randomtimedevent_set
        elif self.event_type == self.EVENT_CASE_PROPERTY_TIME:
            return self.casepropertytimedevent_set
        else:
            raise ValueError("Unexpected value for event_type: %s" % self.event_type)

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

    def get_case_or_none(self, instance):
        from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance

        if isinstance(instance, CaseTimedScheduleInstance):
            return instance.case

        return None

    def get_local_next_event_due_timestamp(self, instance):
        current_event = self.memoized_events[instance.current_event_num]

        days_since_start_date = (
            ((instance.schedule_iteration_num - 1) * self.schedule_length) + current_event.day
        )

        local_time, additional_day_offset = current_event.get_time(case=self.get_case_or_none(instance))
        return datetime.combine(
            self.get_start_date_with_start_offsets(instance) +
            timedelta(days=days_since_start_date + additional_day_offset),
            local_time
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

        local_time, additional_day_offset = current_event.get_time(case=self.get_case_or_none(instance))
        return datetime.combine(target_date + timedelta(days=additional_day_offset), local_time)

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
        for event in self.event_set.all():
            event.content.delete()

        self.event_set.all().delete()

    def get_event_type_from_model_event(self, model_event):
        if isinstance(model_event, TimedEvent):
            return self.EVENT_SPECIFIC_TIME
        elif isinstance(model_event, RandomTimedEvent):
            return self.EVENT_RANDOM_TIME
        elif isinstance(model_event, CasePropertyTimedEvent):
            return self.EVENT_CASE_PROPERTY_TIME
        else:
            raise TypeError("Unexpected type: %s" % type(model_event))

    def create_event_from_model_event(self, model_event):
        if isinstance(model_event, TimedEvent):
            return TimedEvent(
                schedule=self,
                time=model_event.time,
            )
        elif isinstance(model_event, RandomTimedEvent):
            return RandomTimedEvent(
                schedule=self,
                time=model_event.time,
                window_length=model_event.window_length,
            )
        elif isinstance(model_event, CasePropertyTimedEvent):
            return CasePropertyTimedEvent(
                schedule=self,
                case_property_name=model_event.case_property_name,
            )
        else:
            raise TypeError("Unexpected type: %s" % type(model_event))

    @classmethod
    def create_simple_daily_schedule(cls, domain, model_event, content, total_iterations=REPEAT_INDEFINITELY,
            start_offset=0, start_day_of_week=ANY_DAY, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_daily_schedule(model_event, content, total_iterations=total_iterations,
            start_offset=start_offset, start_day_of_week=start_day_of_week, extra_options=extra_options)
        return schedule

    def set_simple_daily_schedule(self, model_event, content, total_iterations=REPEAT_INDEFINITELY, start_offset=0,
            start_day_of_week=ANY_DAY, extra_options=None):
        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.start_offset = start_offset
            self.start_day_of_week = start_day_of_week
            self.schedule_length = 1
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_DAILY
            self.set_extra_scheduling_options(extra_options)
            self.save()

            if content.pk is None:
                content.save()

            event = self.create_event_from_model_event(model_event)
            event.order = 1
            event.day = 0
            event.content = content
            event.save()

    def validate_day_of_week(self, day):
        if not isinstance(day, int) or day < 0 or day > 6:
            raise ValueError("Expected a value between 0 and 6")

    @classmethod
    def create_simple_weekly_schedule(cls, domain, model_event, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_weekly_schedule(model_event, content, days_of_week, start_day_of_week,
            total_iterations=total_iterations, extra_options=extra_options)
        return schedule

    def set_simple_weekly_schedule(self, model_event, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None):
        """
        Sets this TimedSchedule to be a simple weekly schedule where you can choose
        the days of the week on which to send.

        :param model_event: An example event from which to pull timing information; should be an instance of
            a subclass of AbstractTimedEvent
        :param content: The content (corehq.messaging.scheduling.models.Content object) to send
        :days_of_week: A list of integers representing the days of the week on which to send, with
            0 being Monday and 6 being Sunday to match python's datetime.weekday() method
        :start_day_of_week: The day of the week which will be considered the first day of the week for
            scheduling purposes
        :param total_iterations: The total number of weeks to send for
        """
        self.validate_day_of_week(start_day_of_week)

        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.start_day_of_week = start_day_of_week
            self.schedule_length = 7
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_WEEKLY
            self.start_offset = 0
            self.set_extra_scheduling_options(extra_options)
            self.save()

            event_days = []
            for day in days_of_week:
                self.validate_day_of_week(day)
                event_days.append((day - start_day_of_week + 7) % 7)

            order = 1
            for day in sorted(event_days):
                event = self.create_event_from_model_event(model_event)
                event.order = order
                event.day = day

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
    def create_simple_monthly_schedule(cls, domain, model_event, days, content,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_monthly_schedule(model_event, days, content, total_iterations=total_iterations,
            extra_options=extra_options)
        return schedule

    def set_simple_monthly_schedule(self, model_event, days, content, total_iterations=REPEAT_INDEFINITELY,
            extra_options=None):
        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.schedule_length = self.MONTHLY
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_MONTHLY
            self.start_offset = 0
            self.set_extra_scheduling_options(extra_options)
            self.save()

            if content.pk is None:
                content.save()

            order = 1
            for day in days:
                event = self.create_event_from_model_event(model_event)
                event.order = order
                event.day = day

                if order > 1:
                    content.pk = None
                    content.save()

                event.content = content
                event.save()
                order += 1


class AbstractTimedEvent(Event):
    class Meta:
        abstract = True

    schedule = models.ForeignKey('scheduling.TimedSchedule', on_delete=models.CASCADE)
    day = models.IntegerField()

    def get_time(self, case=None):
        """
        Should return (time, additional_day_offset), where:

        time is the local time that the event should take place

        additional_day_offset is the number of days to add to self.day in order to get
        the day on which the event should take place. Most of the time this will be 0,
        but it can be 1 for event definitions that span across a day boundary, for example
        for a RandomTimedEvent whose random time window spans the boundary between two days.
        """
        raise NotImplementedError()

    def get_scheduling_info(self, case=None):
        raise NotImplementedError()


class TimedEvent(AbstractTimedEvent):
    time = models.TimeField()

    def get_time(self, case=None):
        return self.time, 0

    def get_scheduling_info(self, case=None):
        return [self.day, self.time.strftime('%H:%M:%S')]


class RandomTimedEvent(AbstractTimedEvent):
    """
    A RandomTimedEvent defines a window of time in which to select
    a random time to send the content.

    The window starts at self.time and lasts for self.window_length
    minutes.
    """
    time = models.TimeField()
    window_length = models.PositiveIntegerField()

    def get_time(self, case=None):
        choices = list(range(self.window_length))
        minute_offset = random.choice(choices)

        # Create a dummy datetime so that we can use timedelta to add minutes
        dummy_date = date(2000, 1, 1)
        dummy_datetime = datetime.combine(dummy_date, self.time) + timedelta(minutes=minute_offset)
        return dummy_datetime.time(), (dummy_datetime.date() - dummy_date).days

    def get_scheduling_info(self, case=None):
        return [self.day, self.time.strftime('%H:%M:%S'), 'random-window-length-%s' % self.window_length]


class CasePropertyTimedEvent(AbstractTimedEvent):
    """
    A CasePropertyTimedEvent defines the time at which to send the
    content based on the value in a case property.
    """
    case_property_name = models.CharField(max_length=126)

    def get_time(self, case=None):
        if not case:
            raise ValueError("Expected a case")

        default_time = time(12, 0)
        event_time = case.dynamic_case_properties().get(self.case_property_name, '').strip()

        if not re.match('^\d?\d:\d\d', event_time):
            event_time = default_time
        else:
            try:
                event_time = parse(event_time).time()
            except ValueError:
                event_time = default_time

        return event_time, 0

    def get_scheduling_info(self, case=None):
        """
        Include the actual scheduled time (not just the case property name) in
        the scheduling info. This makes the actual time become part of the
        schedule revision so that the framework is responsive to changes
        in the case property's value.
        """
        return [self.day, self.get_time(case=case)[0].strftime('%H:%M:%S')]


class ScheduledBroadcast(Broadcast):
    schedule = models.ForeignKey('scheduling.TimedSchedule', on_delete=models.CASCADE)
    start_date = models.DateField()
