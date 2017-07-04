import calendar
from corehq.messaging.scheduling.exceptions import InvalidMonthlyScheduleConfiguration
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast
from corehq.messaging.scheduling import util
from corehq.util.timezones.conversions import ServerTime, UserTime
from datetime import timedelta, datetime, date
from dimagi.utils.decorators.memoized import memoized
from django.db import models, transaction


class TimedSchedule(Schedule):
    REPEAT_INDEFINITELY = -1
    MONTHLY = -1

    schedule_length = models.IntegerField()
    total_iterations = models.IntegerField()

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
            instance.start_date = ServerTime(util.utcnow()).user_time(instance.timezone).done().date()

        self.set_next_event_due_timestamp(instance)

        if (
            not self.schedule_length == self.MONTHLY and
            not start_date and
            instance.next_event_due < util.utcnow()
        ):
            instance.start_date += timedelta(days=1)
            instance.next_event_due += timedelta(days=1)

    def get_local_next_event_due_timestamp(self, instance):
        current_event = self.memoized_events[instance.current_event_num]

        days_since_start_date = (
            ((instance.schedule_iteration_num - 1) * self.schedule_length) + current_event.day
        )

        return datetime.combine(
            instance.start_date + timedelta(days=days_since_start_date),
            current_event.time
        )

    def get_local_next_event_due_timestamp_for_monthly_schedule(self, instance):
        target_date = None

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

            year = instance.start_date.year + year_offset
            month = instance.start_date.month + month_offset

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

    @classmethod
    def create_simple_daily_schedule(cls, domain, time, content, total_iterations=REPEAT_INDEFINITELY):
        schedule = cls(domain=domain)
        schedule.set_simple_daily_schedule(time, content, total_iterations=total_iterations)
        return schedule

    def set_simple_daily_schedule(self, time, content, total_iterations=REPEAT_INDEFINITELY):
        with transaction.atomic():
            self.schedule_length = 1
            self.total_iterations = total_iterations
            self.save()

            for event in self.timedevent_set.all():
                event.content.delete()

            self.timedevent_set.all().delete()

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

    @classmethod
    def create_simple_monthly_schedule(cls, domain, time, days, content, total_iterations=REPEAT_INDEFINITELY):
        schedule = cls(domain=domain)
        schedule.set_simple_monthly_schedule(time, days, content, total_iterations=total_iterations)
        return schedule

    def set_simple_monthly_schedule(self, time, days, content, total_iterations=REPEAT_INDEFINITELY):
        with transaction.atomic():
            self.schedule_length = self.MONTHLY
            self.total_iterations = total_iterations
            self.save()

            for event in self.timedevent_set.all():
                event.content.delete()

            self.timedevent_set.all().delete()

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
