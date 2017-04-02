from celery.task import task
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    delete_timed_schedule_instance,
    get_alert_schedule_instances_for_schedule,
    get_timed_schedule_instances_for_schedule,
    save_alert_schedule_instance,
    save_timed_schedule_instance,
)


@task(ignore_result=True)
def refresh_alert_schedule_instances(schedule, recipients):
    """
    :param schedule: the AlertSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """

    existing_instances = {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in get_alert_schedule_instances_for_schedule(schedule)
    }

    if existing_instances:
        # Don't refresh AlertSchedules that have already been sent
        # to avoid sending old alerts to new recipients
        return

    for recipient_type, recipient_id in recipients:
        instance = AlertScheduleInstance.create_for_recipient(
            schedule,
            recipient_type,
            recipient_id,
            move_to_next_event_not_in_the_past=False,
        )
        save_alert_schedule_instance(instance)


@task(ignore_result=True)
def refresh_timed_schedule_instances(schedule, recipients, start_date=None):
    """
    :param schedule: the TimedSchedule
    :param start_date: the date to start the TimedSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """

    existing_instances = {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in get_timed_schedule_instances_for_schedule(schedule)
    }

    new_recipients = set(recipients)

    for recipient_type, recipient_id in new_recipients:
        if (recipient_type, recipient_id) not in existing_instances:
            instance = TimedScheduleInstance.create_for_recipient(
                schedule,
                recipient_type,
                recipient_id,
                start_date=start_date,
                move_to_next_event_not_in_the_past=True,
            )
            save_timed_schedule_instance(instance)

    for key, schedule_instance in existing_instances.iteritems():
        if key not in new_recipients:
            delete_timed_schedule_instance(schedule_instance)
        else:
            schedule_instance.recalculate_schedule(schedule, new_start_date=start_date)
            save_timed_schedule_instance(schedule_instance)


@task(ignore_result=True)
def deactivate_schedule_instances(schedule):
    pass


@task(ignore_result=True)
def reactivate_schedule_instances(schedule):
    pass


@task(ignore_result=True)
def delete_broadcast(broadcast):
    pass
