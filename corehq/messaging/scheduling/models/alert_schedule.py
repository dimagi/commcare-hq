from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast
from corehq.messaging.scheduling import util
from datetime import timedelta, time
from memoized import memoized
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

    def delete_related_events(self):
        for event in self.alertevent_set.all():
            event.content.delete()

        self.alertevent_set.all().delete()

    def total_iterations_complete(self, instance):
        # AlertSchedules do not repeat
        return instance.schedule_iteration_num > 1

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

    def soft_delete(self):
        from corehq.messaging.scheduling.tasks import delete_alert_schedule_instances

        with transaction.atomic():
            self.deleted = True
            self.save()
            self.schedule.deleted = True
            self.schedule.save()
            delete_alert_schedule_instances.delay(self.schedule_id)
