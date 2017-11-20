from __future__ import absolute_import
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_alert_schedules(domain):
    for schedule in AlertSchedule.objects.filter(domain=domain):
        for event in schedule.memoized_events:
            event.content.delete()
            event.delete()

        schedule.delete()


@unit_testing_only
def delete_timed_schedules(domain):
    for schedule in TimedSchedule.objects.filter(domain=domain):
        for event in schedule.memoized_events:
            event.content.delete()
            event.delete()

        schedule.delete()
