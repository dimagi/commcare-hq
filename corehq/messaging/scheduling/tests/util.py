from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_alert_schedules(domain):
    for schedule in AlertSchedule.objects.filter(domain=domain):
        schedule.delete_related_events()
        schedule.delete()


@unit_testing_only
def delete_timed_schedules(domain):
    for schedule in TimedSchedule.objects.filter(domain=domain):
        schedule.delete_related_events()
        schedule.delete()
