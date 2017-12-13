from __future__ import absolute_import
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast
from corehq.messaging.scheduling import util
from datetime import timedelta, time
from dimagi.utils.decorators.memoized import memoized
from django.db import models, transaction


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
        instance.next_event_due = util.utcnow()
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

    def delete_related_events(self):
        for event in self.alertevent_set.all():
            event.content.delete()

        self.alertevent_set.all().delete()

    @classmethod
    def create_simple_alert(cls, domain, content, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_simple_alert(content, extra_options=extra_options)
        return schedule

    def set_simple_alert(self, content, extra_options=None):
        with transaction.atomic():
            self.ui_type = Schedule.UI_TYPE_IMMEDIATE
            self.set_extra_scheduling_options(extra_options)
            self.save()

            self.delete_related_events()

            if content.pk is None:
                content.save()

            event = AlertEvent(
                order=1,
                schedule=self,
                time_to_wait=time(0, 0),
            )
            event.content = content
            event.save()


class AlertEvent(Event):
    schedule = models.ForeignKey('scheduling.AlertSchedule', on_delete=models.CASCADE)
    time_to_wait = models.TimeField()


class ImmediateBroadcast(Broadcast):
    schedule = models.ForeignKey('scheduling.AlertSchedule', on_delete=models.CASCADE)
