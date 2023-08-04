import calendar
import hashlib
import json
import random
import re
from copy import deepcopy

from django.db import models, transaction

from corehq.apps.data_interfaces.utils import property_references_parent
from corehq.messaging.scheduling.exceptions import InvalidMonthlyScheduleConfiguration
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast, Content
from corehq.messaging.scheduling import util
from corehq.sql_db.util import create_unique_index_name
from corehq.util.timezones.conversions import UserTime
from datetime import timedelta, datetime, date, time
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from memoized import memoized


class TimedSchedule(Schedule):
    REPEAT_INDEFINITELY = -1

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

    # If repeat_every is positive, it represents the number of days
    # after which to repeat all the schedule's events.
    # If repeat_every is negative, it represents the number of months
    # after which to repeat all the schedule's events.
    repeat_every = models.IntegerField()

    # total_iterations represents the total number of times to iterate
    # through the schedule's events; a value of 1 means the events do
    # not repeat
    total_iterations = models.IntegerField()
    start_offset = models.IntegerField(default=0)
    start_day_of_week = models.IntegerField(default=ANY_DAY)

    # For the purposes of displaying schedules in the UI, it's expected that
    # all events related to a given schedule are of the same type which is stored
    # here. But the framework should handle a schedule with mixed event types or
    # mixed content types.
    event_type = models.CharField(max_length=50, default=EVENT_SPECIFIC_TIME)

    class Meta:
        indexes = [
            models.Index(fields=['deleted_on'],
                         name=create_unique_index_name('scheduling',
                                                       'timedschedule',
                                                       ['deleted_on']),
                         condition=models.Q(deleted_on__isnull=False))
        ]

    def get_schedule_revision(self, case=None):
        """
        The schedule revision is a hash of all information pertaining to
        scheduling. Information unrelated to scheduling, such as the content
        being sent at each event, is excluded. This is mainly used to determine
        when a TimedScheduleInstance should recalculate its schedule.
        """
        result = [
            self.repeat_every,
            self.total_iterations,
            self.start_offset,
            self.start_day_of_week,
            [e.get_scheduling_info(case=case) for e in self.memoized_events],
        ]

        if self.use_utc_as_default_timezone:
            result.append('UTC_DEFAULT')

        schedule_info = json.dumps(result).encode('utf-8')
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

    @property
    def is_monthly(self):
        """
        For the purposes of repeat_every, the schedule can really be considered to
        be either "daily" or "monthly", since "weekly" is a special case of "daily"
        which repeats every 7 days, and "yearly" is a special case of "monthly"
        which repeats every 12 months.
        """
        return self.repeat_every < 0

    def get_weekdays(self):
        """
        Returns the weekdays (0-6 meaning Monday-Sunday) that this weekly schedule
        sends on.
        """
        if self.ui_type != self.UI_TYPE_WEEKLY:
            raise ValueError("Expected simple weekly schedule")

        return [(self.start_day_of_week + e.day) % 7 for e in self.memoized_events]

    def set_first_event_due_timestamp(self, instance, start_date=None):
        """
        If start_date is None, we set it automatically ensuring that
        self.next_event_due does not get set in the past for the first
        event.
        """
        if start_date:
            instance.start_date = start_date
        else:
            instance.start_date = instance.get_today_for_recipient(self)

        self.set_next_event_due_timestamp(instance)

        # If there was no specific start date for the schedule, we
        # start it today. But that can cause us to put the first event
        # in the past if it has already passed for the day. So if that
        # happens, push the schedule out by 1 day for daily schedules,
        # 1 week for weekly schedules, or 1 month for monthly schedules.
        if (
            not start_date and
            instance.next_event_due < util.utcnow()
        ):
            if self.is_monthly:
                # Monthly
                new_start_date = instance.start_date + relativedelta(months=1)
                instance.start_date = date(new_start_date.year, new_start_date.month, 1)
                # Current event and schedule iteration might be updated
                # in the call to set_next_event_due_timestamp, so reset them
                instance.current_event_num = 0
                instance.schedule_iteration_num = 1
            elif self.start_day_of_week == self.ANY_DAY:
                # Daily
                instance.start_date += timedelta(days=1)
            else:
                # Weekly
                instance.start_date += timedelta(days=7)

            self.set_next_event_due_timestamp(instance)

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
        if self.repeat_every <= 0:
            raise ValueError("Expected positive value for repeat_every in a daily or weekly schedule")

        current_event = self.memoized_events[instance.current_event_num]

        days_since_start_date = (
            ((instance.schedule_iteration_num - 1) * self.repeat_every) + current_event.day
        )

        local_time, additional_day_offset = current_event.get_time(case=self.get_case_or_none(instance))
        return datetime.combine(
            self.get_start_date_with_start_offsets(instance) +
            timedelta(days=days_since_start_date + additional_day_offset),
            local_time
        )

    def get_local_next_event_due_timestamp_for_monthly_schedule(self, instance):
        if self.repeat_every >= 0:
            raise ValueError("Expected negative value for repeat_every in a monthly schedule")

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

            months_since_start_date = (instance.schedule_iteration_num - 1) * (-1 * self.repeat_every)
            year = start_date_with_offset.year
            month = start_date_with_offset.month + months_since_start_date

            while month > 12:
                year += 1
                month -= 12

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
        if self.is_monthly:
            user_timestamp = self.get_local_next_event_due_timestamp_for_monthly_schedule(instance)
        else:
            user_timestamp = self.get_local_next_event_due_timestamp(instance)

        instance.next_event_due = (
            UserTime(user_timestamp, instance.get_timezone(self))
            .server_time()
            .done()
            .replace(tzinfo=None)
        )

    def get_current_event_content(self, instance):
        current_event = self.memoized_events[instance.current_event_num]
        return current_event.memoized_content

    def total_iterations_complete(self, instance):
        return (
            self.total_iterations != self.REPEAT_INDEFINITELY and
            instance.schedule_iteration_num > self.total_iterations
        )

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

    def check_positive_repeat_every(self, repeat_every):
        """
        The value that gets stored to this model for repeat_every can be
        negative to represent monthly schedules (see comment on repeat_every).

        But when using util methods to create and edit schedules,
        we always use a positive value for repeat_every param to make it
        easier to setup schedules.
        """
        if repeat_every <= 0:
            raise ValueError("Expected positive value, got %s" % repeat_every)

    @classmethod
    def create_simple_daily_schedule(cls, domain, model_event, content, total_iterations=REPEAT_INDEFINITELY,
            start_offset=0, start_day_of_week=ANY_DAY, extra_options=None, repeat_every=1):
        schedule = cls(domain=domain)
        schedule.set_simple_daily_schedule(model_event, content, total_iterations=total_iterations,
            start_offset=start_offset, start_day_of_week=start_day_of_week, extra_options=extra_options,
            repeat_every=repeat_every)
        return schedule

    def set_simple_daily_schedule(self, model_event, content, total_iterations=REPEAT_INDEFINITELY, start_offset=0,
            start_day_of_week=ANY_DAY, extra_options=None, repeat_every=1):
        self.check_positive_repeat_every(repeat_every)

        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.start_offset = start_offset
            self.start_day_of_week = start_day_of_week
            self.repeat_every = repeat_every
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

    @classmethod
    def create_custom_daily_schedule(cls, domain, event_and_content_objects, total_iterations=REPEAT_INDEFINITELY,
            start_offset=0, start_day_of_week=ANY_DAY, extra_options=None, repeat_every=1):
        schedule = cls(domain=domain)
        schedule.set_custom_daily_schedule(event_and_content_objects, total_iterations=total_iterations,
            start_offset=start_offset, start_day_of_week=start_day_of_week, extra_options=extra_options,
            repeat_every=repeat_every)
        return schedule

    def set_custom_daily_schedule(self, event_and_content_objects, total_iterations=REPEAT_INDEFINITELY,
            start_offset=0, start_day_of_week=ANY_DAY, extra_options=None, repeat_every=1):
        """
        :param event_and_content_objects: A list of (event, content) tuples where event is
        an instance of a subclass of AbstractTimedEvent and content is an instance of a
        subclass of Content. These tuples should already be in the right order, and the
        order attribute of each event will be set according to the order in this list.
        It's also expected that each event is of the same type (i.e., TimedEvent, RandomTimedEvent,
        or CasePropertyTimedEvent) for the purposes of displaying this schedule in the UI.

        :param total_iterations: the total iterations of the schedule to perform

        :param start_offset: the start offset

        :param start_day_of_week: the start day of the week

        :param extra_options: any extra options that will be passed to set_extra_scheduling_options

        :param repeat_every: this should be the number of days in the schedule and will
        dictate how often the schedule repeats
        """

        self.check_positive_repeat_every(repeat_every)

        if len(event_and_content_objects) == 0:
            raise ValueError("Expected at least one (event, content) tuple")

        if repeat_every <= max([e[0].day for e in event_and_content_objects]):
            raise ValueError("repeat_every must be large enough to cover all days in the schedule")

        with transaction.atomic():
            self.delete_related_events()

            self.ui_type = self.UI_TYPE_CUSTOM_DAILY
            self.event_type = self.get_event_type_from_model_event(event_and_content_objects[0][0])
            self.start_offset = start_offset
            self.start_day_of_week = start_day_of_week
            self.repeat_every = repeat_every
            self.total_iterations = total_iterations
            self.set_extra_scheduling_options(extra_options)
            self.save()

            # passing `start` just controls where order starts counting at, it doesn't
            # cause elements to be skipped
            for order, event_and_content in enumerate(event_and_content_objects, start=1):
                event, content = event_and_content

                if not isinstance(event, AbstractTimedEvent):
                    raise TypeError("Expected AbstractTimedEvent")

                if not isinstance(content, Content):
                    raise TypeError("Expected Content")

                content.save()
                event.schedule = self
                event.content = content
                event.order = order
                event.save()

    def validate_day_of_week(self, day):
        if not isinstance(day, int) or day < 0 or day > 6:
            raise ValueError("Expected a value between 0 and 6")

    @classmethod
    def create_simple_weekly_schedule(cls, domain, model_event, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None, repeat_every=1):
        schedule = cls(domain=domain)
        schedule.set_simple_weekly_schedule(model_event, content, days_of_week, start_day_of_week,
            total_iterations=total_iterations, extra_options=extra_options, repeat_every=repeat_every)
        return schedule

    def set_simple_weekly_schedule(self, model_event, content, days_of_week, start_day_of_week,
            total_iterations=REPEAT_INDEFINITELY, extra_options=None, repeat_every=1):
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
        :param repeat_every: A value of 1 means repeat every week; 2 means repeat every other week, etc.
        """
        self.validate_day_of_week(start_day_of_week)
        self.check_positive_repeat_every(repeat_every)

        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.start_day_of_week = start_day_of_week
            self.repeat_every = repeat_every * 7
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
            total_iterations=REPEAT_INDEFINITELY, extra_options=None, repeat_every=1):
        schedule = cls(domain=domain)
        schedule.set_simple_monthly_schedule(model_event, days, content, total_iterations=total_iterations,
            extra_options=extra_options, repeat_every=repeat_every)
        return schedule

    def set_simple_monthly_schedule(self, model_event, days, content, total_iterations=REPEAT_INDEFINITELY,
            extra_options=None, repeat_every=1):
        """
        :param repeat_every: A value of 1 means repeat every month; 2 means repeat every other month, etc.
        """
        self.check_positive_repeat_every(repeat_every)

        with transaction.atomic():
            self.delete_related_events()

            self.event_type = self.get_event_type_from_model_event(model_event)
            self.repeat_every = -1 * repeat_every
            self.total_iterations = total_iterations
            self.ui_type = Schedule.UI_TYPE_MONTHLY
            self.start_offset = 0
            self.start_day_of_week = self.ANY_DAY
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

    @property
    def references_parent_case(self):
        if super(TimedSchedule, self).references_parent_case:
            return True

        for event in self.memoized_events:
            if isinstance(event, CasePropertyTimedEvent) and property_references_parent(event.case_property_name):
                return True

        return False


class AbstractTimedEvent(Event):
    class Meta(object):
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

    def create_copy(self):
        """
        See Event.create_copy() for docstring.
        """
        return TimedEvent(
            day=self.day,
            time=deepcopy(self.time),
        )

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

    def create_copy(self):
        """
        See Event.create_copy() for docstring.
        """
        return RandomTimedEvent(
            day=self.day,
            time=deepcopy(self.time),
            window_length=self.window_length,
        )

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

    def create_copy(self):
        """
        See Event.create_copy() for docstring.
        """
        return CasePropertyTimedEvent(
            day=self.day,
            case_property_name=self.case_property_name,
        )

    def get_time(self, case=None):
        if not case:
            raise ValueError("Expected a case")

        default_time = time(12, 0)
        event_time = case.dynamic_case_properties().get(self.case_property_name, '').strip()

        if not re.match(r'^\d?\d:\d\d', event_time):
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

    class Meta:
        indexes = [
            models.Index(fields=['deleted_on'],
                         name=create_unique_index_name('scheduling',
                                                       'scheduledbroadcast',
                                                       ['deleted_on']),
                         condition=models.Q(deleted_on__isnull=False))
        ]

    def soft_delete(self):
        from corehq.messaging.scheduling.tasks import delete_timed_schedule_instances

        with transaction.atomic():
            self.deleted = True
            self.deleted_on = datetime.utcnow()
            self.save()
            self.schedule.deleted = True
            self.schedule.deleted_on = datetime.utcnow()
            self.schedule.save()
            delete_timed_schedule_instances.delay(self.schedule_id.hex)
