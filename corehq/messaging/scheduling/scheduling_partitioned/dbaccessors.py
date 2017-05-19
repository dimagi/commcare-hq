from corehq.sql_db.util import (
    get_object_from_partitioned_database,
    save_object_to_partitioned_database,
    delete_object_from_partitioned_database,
    run_query_across_partitioned_databases,
    get_db_alias_for_partitioned_doc,
)
from django.db.models import Q
from uuid import UUID


def _validate_class(obj, cls):
    """
    :param cls: A type or tuple of types to check the type of obj against
    """
    if not isinstance(obj, cls):
        raise ValueError("Expected an instance of %s" % str(cls))


def _validate_uuid(value):
    _validate_class(value, UUID)


def get_alert_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_uuid(schedule_instance_id)
    return get_object_from_partitioned_database(
        AlertScheduleInstance,
        schedule_instance_id,
        'schedule_instance_id'
    )


def get_timed_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_uuid(schedule_instance_id)
    return get_object_from_partitioned_database(
        TimedScheduleInstance,
        schedule_instance_id,
        'schedule_instance_id'
    )


def save_alert_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(instance, AlertScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    save_object_to_partitioned_database(instance, instance.schedule_instance_id)


def save_timed_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(instance, TimedScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    save_object_to_partitioned_database(instance, instance.schedule_instance_id)


def delete_alert_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(instance, AlertScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    delete_object_from_partitioned_database(instance, instance.schedule_instance_id)


def delete_timed_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(instance, TimedScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    delete_object_from_partitioned_database(instance, instance.schedule_instance_id)


def _get_active_schedule_instance_ids(cls, start_timestamp, end_timestamp):
    active_filter = Q(
        active=True,
        next_event_due__gt=start_timestamp,
        next_event_due__lte=end_timestamp,
    )
    for schedule_instance_id in run_query_across_partitioned_databases(
        cls,
        active_filter,
        values=['schedule_instance_id']
    ):
        yield schedule_instance_id


def get_active_alert_schedule_instance_ids(start_timestamp, end_timestamp):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    return _get_active_schedule_instance_ids(AlertScheduleInstance, start_timestamp, end_timestamp)


def get_active_timed_schedule_instance_ids(start_timestamp, end_timestamp):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    return _get_active_schedule_instance_ids(TimedScheduleInstance, start_timestamp, end_timestamp)


def get_alert_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import AlertSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(schedule, AlertSchedule)
    return run_query_across_partitioned_databases(
        AlertScheduleInstance,
        Q(alert_schedule_id=schedule.schedule_id)
    )


def get_timed_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import TimedSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(schedule, TimedSchedule)
    return run_query_across_partitioned_databases(
        TimedScheduleInstance,
        Q(timed_schedule_id=schedule.schedule_id)
    )


def get_case_alert_schedule_instances_for_schedule(case_id, schedule):
    from corehq.messaging.scheduling.models import AlertSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import CaseAlertScheduleInstance

    _validate_class(schedule, AlertSchedule)
    db_name = get_db_alias_for_partitioned_doc(case_id)
    return CaseAlertScheduleInstance.objects.using(db_name).filter(
        case_id=case_id,
        alert_schedule_id=schedule.schedule_id
    )


def get_case_timed_schedule_instances_for_schedule(case_id, schedule):
    from corehq.messaging.scheduling.models import TimedSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance

    _validate_class(schedule, TimedSchedule)
    db_name = get_db_alias_for_partitioned_doc(case_id)
    return CaseTimedScheduleInstance.objects.using(db_name).filter(
        case_id=case_id,
        timed_schedule_id=schedule.schedule_id
    )


def save_case_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    _validate_class(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance))
    _validate_uuid(instance.schedule_instance_id)
    save_object_to_partitioned_database(instance, instance.case_id)


def delete_case_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    _validate_class(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance))
    delete_object_from_partitioned_database(instance, instance.case_id)
