from __future__ import absolute_import
from celery.task import task
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    ScheduledBroadcast,
    AlertSchedule,
    TimedSchedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    delete_alert_schedule_instance,
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
import six


def _get_any_value_or_none(from_dict):
    if from_dict:
        return six.next(six.itervalues(from_dict))

    return None


def _recipient_instance_dict(instances):
    return {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in instances
    }


@task(ignore_result=True)
def refresh_alert_schedule_instances(schedule_id, recipients):
    """
    :param schedule_id: the AlertSchedule schedule_id
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """
    schedule = AlertSchedule.objects.get(schedule_id=schedule_id)

    existing_instances = _recipient_instance_dict(get_alert_schedule_instances_for_schedule(schedule))
    model_instance = _get_any_value_or_none(existing_instances)

    recipients = set(convert_to_tuple_of_tuples(recipients))
    for recipient_type, recipient_id in recipients:
        if (recipient_type, recipient_id) in existing_instances:
            continue

        if model_instance:
            instance = AlertScheduleInstance.copy_for_recipient(model_instance, recipient_type, recipient_id)
        else:
            instance = AlertScheduleInstance.create_for_recipient(
                schedule,
                recipient_type,
                recipient_id,
                move_to_next_event_not_in_the_past=False,
            )
        save_alert_schedule_instance(instance)

    for recipient_type_and_id, instance in six.iteritems(existing_instances):
        if recipient_type_and_id not in recipients:
            delete_alert_schedule_instance(instance)


@task(ignore_result=True)
def refresh_timed_schedule_instances(schedule_id, recipients, start_date=None):
    """
    :param schedule_id: the TimedSchedule schedule_id
    :param start_date: the date to start the TimedSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """
    schedule = TimedSchedule.objects.get(schedule_id=schedule_id)

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
                schedule_revision=schedule.memoized_schedule_revision,
            )
            save_timed_schedule_instance(instance)

    for key, schedule_instance in six.iteritems(existing_instances):
        if key not in new_recipients:
            delete_timed_schedule_instance(schedule_instance)
        elif (
            (start_date and start_date != schedule_instance.start_date) or
            (schedule_instance.schedule_revision != schedule.memoized_schedule_revision)
        ):
            new_start_date = start_date or schedule_instance.start_date
            schedule_instance.recalculate_schedule(schedule, new_start_date=new_start_date)
            save_timed_schedule_instance(schedule_instance)


def convert_to_tuple_of_tuples(list_of_lists):
    list_of_tuples = [tuple(item) for item in list_of_lists]
    return tuple(list_of_tuples)


def refresh_case_alert_schedule_instances(case, schedule, action_definition, rule):
    """
    :param case: the CommCareCase/SQL
    :param schedule: the AlertSchedule
    :param action_definition: the CreateScheduleInstanceActionDefinition that is
    causing the schedule instances to be refreshed
    :param rule: the AutomaticUpdateRule that is causing the schedule instances
    to be refreshed
    """

    existing_instances = _recipient_instance_dict(
        get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
    )
    model_instance = _get_any_value_or_none(existing_instances)

    recipients = set(convert_to_tuple_of_tuples(action_definition.recipients))
    for recipient_type, recipient_id in recipients:
        if (recipient_type, recipient_id) in existing_instances:
            continue

        if model_instance:
            instance = CaseAlertScheduleInstance.copy_for_recipient(model_instance, recipient_type, recipient_id)
        else:
            instance = CaseAlertScheduleInstance.create_for_recipient(
                schedule,
                recipient_type,
                recipient_id,
                move_to_next_event_not_in_the_past=False,
                case_id=case.case_id,
                rule_id=rule.pk
            )
        save_case_schedule_instance(instance)

    for recipient_type_and_id, instance in six.iteritems(existing_instances):
        if recipient_type_and_id not in recipients:
            delete_case_schedule_instance(instance)


def refresh_case_timed_schedule_instances(case, schedule, action_definition, rule, start_date=None):
    """
    :param case: the CommCareCase/SQL
    :param schedule: the TimedSchedule
    :param action_definition: the CreateScheduleInstanceActionDefinition that is
    causing the schedule instances to be refreshed
    :param rule: the AutomaticUpdateRule that is causing the schedule instances
    to be refreshed
    :param start_date: the date to start the TimedSchedule
    """

    existing_instances = {
        (instance.recipient_type, instance.recipient_id): instance
        for instance in get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
    }

    recipients = convert_to_tuple_of_tuples(action_definition.recipients)
    new_recipients = set(recipients)

    # Only allow dynamic case properties here since the formatting of
    # the value is very important if we're comparing from one time to
    # the next
    reset_case_property_value = (
        case.dynamic_case_properties().get(action_definition.reset_case_property_name, '')
        if action_definition.reset_case_property_name else None
    )

    for recipient_type, recipient_id in new_recipients:
        if (recipient_type, recipient_id) not in existing_instances:
            instance = CaseTimedScheduleInstance.create_for_recipient(
                schedule,
                recipient_type,
                recipient_id,
                start_date=start_date,
                move_to_next_event_not_in_the_past=True,
                case_id=case.case_id,
                rule_id=rule.pk,
                last_reset_case_property_value=reset_case_property_value,
                schedule_revision=schedule.memoized_schedule_revision,
            )
            save_case_schedule_instance(instance)

    for key, schedule_instance in six.iteritems(existing_instances):
        if key not in new_recipients:
            delete_case_schedule_instance(schedule_instance)
        else:
            if action_definition.reset_case_property_name:
                if reset_case_property_value != schedule_instance.last_reset_case_property_value:
                    schedule_instance.recalculate_schedule(schedule)
                    schedule_instance.last_reset_case_property_value = reset_case_property_value
                    save_case_schedule_instance(schedule_instance)
                    continue

            if (
                (start_date and start_date != schedule_instance.start_date) or
                (schedule_instance.schedule_revision != schedule.memoized_schedule_revision)
            ):
                new_start_date = start_date or schedule_instance.start_date
                schedule_instance.recalculate_schedule(schedule, new_start_date=new_start_date)
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
    """
    :return: True if the event was handled, otherwise False
    """
    if instance.active and instance.next_event_due < datetime.utcnow():
        instance.handle_current_event()
        save_function(instance)
        return True

    return False


def update_broadcast_last_sent_timestamp(broadcast_class, schedule_id):
    broadcast_class.objects.filter(schedule_id=schedule_id).update(last_sent_timestamp=datetime.utcnow())


@no_result_task(queue='reminder_queue')
def handle_alert_schedule_instance(schedule_instance_id):
    try:
        instance = get_alert_schedule_instance(schedule_instance_id)
    except AlertScheduleInstance.DoesNotExist:
        return

    if _handle_schedule_instance(instance, save_alert_schedule_instance):
        update_broadcast_last_sent_timestamp(ImmediateBroadcast, instance.alert_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_timed_schedule_instance(schedule_instance_id):
    try:
        instance = get_timed_schedule_instance(schedule_instance_id)
    except TimedScheduleInstance.DoesNotExist:
        return

    if _handle_schedule_instance(instance, save_timed_schedule_instance):
        update_broadcast_last_sent_timestamp(ScheduledBroadcast, instance.timed_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_case_alert_schedule_instance(case_id, schedule_instance_id):
    try:
        instance = get_case_schedule_instance(CaseAlertScheduleInstance, case_id, schedule_instance_id)
    except CaseAlertScheduleInstance.DoesNotExist:
        return

    _handle_schedule_instance(instance, save_case_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_case_timed_schedule_instance(case_id, schedule_instance_id):
    try:
        instance = get_case_schedule_instance(CaseTimedScheduleInstance, case_id, schedule_instance_id)
    except CaseTimedScheduleInstance.DoesNotExist:
        return

    _handle_schedule_instance(instance, save_case_schedule_instance)
