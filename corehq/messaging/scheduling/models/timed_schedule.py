from corehq.messaging.scheduling.models.abstract import Schedule, Event
from corehq.util.timezones.conversions import ServerTime, UserTime
from datetime import timedelta, datetime
from dimagi.utils.decorators.memoized import memoized
from django.db import models


class TimedSchedule(Schedule):
    REPEAT_INDEFINITELY = -1

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
            instance.start_date = ServerTime(datetime.utcnow()).user_time(instance.timezone).done().date()

        self.set_next_event_due_timestamp(instance)

        if not start_date and instance.next_event_due < datetime.utcnow():
            instance.start_date += timedelta(days=1)
            instance.next_event_due += timedelta(days=1)

    def set_next_event_due_timestamp(self, instance):
        current_event = self.memoized_events[instance.current_event_num]
        days_since_start_date = (
            ((instance.schedule_iteration_num - 1) * self.schedule_length) + current_event.day
        )

        timestamp = datetime.combine(
            instance.start_date + timedelta(days=days_since_start_date),
            current_event.time
        )
        instance.next_event_due = (
            UserTime(timestamp, instance.timezone)
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
            self.active = False

    @classmethod
    def create_daily_schedule(cls, domain, schedule_length=1, total_iterations=REPEAT_INDEFINITELY):
        return cls.objects.create(
            domain=domain,
            schedule_length=schedule_length,
            total_iterations=total_iterations
        )

    def add_event(self, day, time, content, order=None):
        if order is None:
            order = self.timedevent_set.count()

        if content.pk is None:
            content.save()

        event = TimedEvent(
            schedule=self,
            order=order,
            day=day,
            time=time
        )
        event.content = content
        event.save()
        return self


class TimedEvent(Event):
    schedule = models.ForeignKey('scheduling.TimedSchedule', on_delete=models.CASCADE)
    day = models.IntegerField()
    time = models.TimeField()
