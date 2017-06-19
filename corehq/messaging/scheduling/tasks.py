from celery.task import task
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    delete_timed_schedule_instance,
    get_alert_schedule_instances_for_schedule,
    get_timed_schedule_instances_for_schedule,
    get_alert_schedule_instance,
    save_alert_schedule_instance,
    get_timed_schedule_instance,
    save_timed_schedule_instance,
    get_case_alert_schedule_instances_for_schedule,
    get_case_timed_schedule_instances_for_schedule,
    get_case_schedule_instance,
    save_case_schedule_instance,
    delete_case_schedule_instance,
)
from corehq.util.celery_utils import no_result_task
from datetime import datetime


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

    recipients = set(convert_to_tuple_of_tuples(recipients))
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

    recipients = convert_to_tuple_of_tuples(recipients)
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


def convert_to_tuple_of_tuples(list_of_lists):
    list_of_tuples = [tuple(item) for item in list_of_lists]
    return tuple(list_of_tuples)


def refresh_case_alert_schedule_instances(case_id, schedule, recipients, rule):
    """
    :param case_id: the case_id of the CommCareCase/SQL
    :param schedule: the AlertSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    or CaseScheduleInstanceMixin.recipient
    """

    existing_instances = {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in get_case_alert_schedule_instances_for_schedule(case_id, schedule)
    }

    if existing_instances:
        # Don't refresh AlertSchedules that have already been sent
        # to avoid sending old alerts to new recipients
        return

    recipients = set(convert_to_tuple_of_tuples(recipients))
    for recipient_type, recipient_id in recipients:
        instance = CaseAlertScheduleInstance.create_for_recipient(
            schedule,
            recipient_type,
            recipient_id,
            move_to_next_event_not_in_the_past=False,
            case_id=case_id,
            rule_id=rule.pk
        )
        save_case_schedule_instance(instance)


def refresh_case_timed_schedule_instances(case_id, schedule, recipients, rule, start_date=None):
    """
    :param case_id: the case_id of the CommCareCase/SQL
    :param schedule: the TimedSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    or CaseScheduleInstanceMixin.recipient
    :param start_date: the date to start the TimedSchedule
    """

    existing_instances = {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in get_case_timed_schedule_instances_for_schedule(case_id, schedule)
    }

    recipients = convert_to_tuple_of_tuples(recipients)
    new_recipients = set(recipients)

    for recipient_type, recipient_id in new_recipients:
        if (recipient_type, recipient_id) not in existing_instances:
            instance = CaseTimedScheduleInstance.create_for_recipient(
                schedule,
                recipient_type,
                recipient_id,
                start_date=start_date,
                move_to_next_event_not_in_the_past=True,
                case_id=case_id,
                rule_id=rule.pk
            )
            save_case_schedule_instance(instance)

    for key, schedule_instance in existing_instances.iteritems():
        if key not in new_recipients:
            delete_case_schedule_instance(schedule_instance)
        else:
            schedule_instance.recalculate_schedule(schedule, new_start_date=start_date)
            save_case_schedule_instance(schedule_instance)


@task(ignore_result=True)
def deactivate_schedule_instances(schedule):
    pass


@task(ignore_result=True)
def reactivate_schedule_instances(schedule):
    pass


@task(ignore_result=True)
def delete_broadcast(broadcast):
    pass


def _handle_schedule_instance(instance, save_function):
    if instance.active and instance.next_event_due < datetime.utcnow():
        instance.handle_current_event()
        save_function(instance)


@no_result_task(queue='reminder_queue')
def handle_alert_schedule_instance(schedule_instance_id):
    instance = get_alert_schedule_instance(schedule_instance_id)
    _handle_schedule_instance(instance, save_alert_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_timed_schedule_instance(schedule_instance_id):
    instance = get_timed_schedule_instance(schedule_instance_id)
    _handle_schedule_instance(instance, save_timed_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_case_alert_schedule_instance(case_id, schedule_instance_id):
    instance = get_case_schedule_instance(CaseAlertScheduleInstance, case_id, schedule_instance_id)
    _handle_schedule_instance(instance, save_case_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_case_timed_schedule_instance(case_id, schedule_instance_id):
    instance = get_case_schedule_instance(CaseTimedScheduleInstance, case_id, schedule_instance_id)
    _handle_schedule_instance(instance, save_case_schedule_instance)
