from corehq.messaging.scheduling.models.abstract import Schedule, Event
from datetime import timedelta, datetime
from dimagi.utils.decorators.memoized import memoized
from django.db import models


class AlertSchedule(Schedule):

    @property
    @memoized
    def memoized_events(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the event set is not changing.
        """
        return list(self.alertevent_set.order_by('order'))

    def set_first_event_due_timestamp(self, instance, start_date=None):
        instance.next_event_due = datetime.utcnow()
        self.set_next_event_due_timestamp(instance)

    def set_next_event_due_timestamp(self, instance):
        current_event = self.memoized_events[instance.current_event_num]
        instance.next_event_due += timedelta(
            hours=current_event.time_to_wait.hour,
            minutes=current_event.time_to_wait.minute
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

        if instance.schedule_iteration_num > 1:
            # AlertSchedules do not repeat
            instance.active = False

    @classmethod
    def create(cls, domain):
        return cls.objects.create(domain=domain)

    def add_event(self, time_to_wait, content, order=None):
        if order is None:
            order = self.alertevent_set.count() + 1

        if content.pk is None:
            content.save()

        event = AlertEvent(
            schedule=self,
            order=order,
            time_to_wait=time_to_wait
        )
        event.content = content
        event.save()
        return self


class AlertEvent(Event):
    schedule = models.ForeignKey('scheduling.AlertSchedule', on_delete=models.CASCADE)
    time_to_wait = models.TimeField()
