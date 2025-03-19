from django.db import models, transaction

from corehq.messaging.scheduling.models.abstract import Schedule, Event, Broadcast, Content
from corehq.messaging.scheduling import util
from datetime import timedelta, datetime
from memoized import memoized

from corehq.sql_db.util import create_unique_index_name


class AlertSchedule(Schedule):

    class Meta:
        indexes = [
            models.Index(fields=['deleted_on'],
                         name=create_unique_index_name('scheduling',
                                                       'alertschedule',
                                                       ['deleted_on']),
                         condition=models.Q(deleted_on__isnull=False))
        ]

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
        instance.next_event_due += timedelta(minutes=current_event.minutes_to_wait)

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
                minutes_to_wait=0,
            )
            event.content = content
            event.save()

    @classmethod
    def create_custom_alert(cls, domain, event_and_content_objects, extra_options=None):
        schedule = cls(domain=domain)
        schedule.set_custom_alert(event_and_content_objects, extra_options=extra_options)
        return schedule

    def set_custom_alert(self, event_and_content_objects, extra_options=None):
        if len(event_and_content_objects) == 0:
            raise ValueError("Expected at least one (event, content) tuple")

        with transaction.atomic():
            self.ui_type = Schedule.UI_TYPE_CUSTOM_IMMEDIATE
            self.set_extra_scheduling_options(extra_options)
            self.save()

            self.delete_related_events()

            # passing `start` just controls where order starts counting at, it doesn't
            # cause elements to be skipped
            for order, event_and_content in enumerate(event_and_content_objects, start=1):
                event, content = event_and_content

                if not isinstance(event, AlertEvent):
                    raise TypeError("Expected AlertEvent")

                if not isinstance(content, Content):
                    raise TypeError("Expected Content")

                content.save()
                event.schedule = self
                event.content = content
                event.order = order
                event.save()


class AlertEvent(Event):
    schedule = models.ForeignKey('scheduling.AlertSchedule', on_delete=models.CASCADE)
    minutes_to_wait = models.IntegerField()

    def create_copy(self):
        """
        See Event.create_copy() for docstring.
        """
        return AlertEvent(
            minutes_to_wait=self.minutes_to_wait,
        )


class ImmediateBroadcast(Broadcast):
    schedule = models.ForeignKey('scheduling.AlertSchedule', on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['deleted_on'],
                         name=create_unique_index_name('scheduling',
                                                       'immediatebroadcast',
                                                       ['deleted_on']),
                         condition=models.Q(deleted_on__isnull=False))
        ]

    def soft_delete(self):
        from corehq.messaging.scheduling.tasks import delete_alert_schedule_instances

        with transaction.atomic():
            self.deleted = True
            self.deleted_on = datetime.utcnow()
            self.save()
            self.schedule.deleted = True
            self.schedule.deleted_on = datetime.utcnow()
            self.schedule.save()
            delete_alert_schedule_instances.delay(self.schedule_id.hex)
