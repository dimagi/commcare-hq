from corehq.messaging.scheduling.exceptions import UnknownScheduleType
from corehq.sql_db.util import (
    get_object_from_partitioned_database,
    save_object_to_partitioned_database,
    delete_object_from_partitioned_database,
    run_query_across_partitioned_databases,
)
from django.db.models import Q
from uuid import UUID


def _validate_schedule_instance(obj):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    if not isinstance(obj, ScheduleInstance):
        raise ValueError("Expected an instance of ScheduleInstance")


def _validate_uuid(value):
    if not isinstance(value, UUID):
        raise ValueError("Expected an instance of UUID")


def get_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    _validate_uuid(schedule_instance_id)
    return get_object_from_partitioned_database(ScheduleInstance, schedule_instance_id, 'schedule_instance_id')


def save_schedule_instance(instance):
    _validate_schedule_instance(instance)
    _validate_uuid(instance.schedule_instance_id)
    save_object_to_partitioned_database(instance, instance.schedule_instance_id)


def delete_schedule_instance(instance):
    _validate_schedule_instance(instance)
    _validate_uuid(instance.schedule_instance_id)
    delete_object_from_partitioned_database(instance, instance.schedule_instance_id)


def get_active_schedule_instance_ids(start_timestamp, end_timestamp):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    active_filter = Q(
        active=True,
        next_event_due__gt=start_timestamp,
        next_event_due__lte=end_timestamp,
    )
    for schedule_instance_id in run_query_across_partitioned_databases(
        ScheduleInstance,
        active_filter,
        values=['schedule_instance_id']
    ):
        yield schedule_instance_id


def get_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule, ScheduleForeignKeyMixin
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    if isinstance(schedule, AlertSchedule):
        schedule_filter = Q(alert_schedule_id=schedule.pk)
    elif isinstance(schedule, TimedSchedule):
        schedule_filter = Q(timed_schedule_id=schedule.pk)
    else:
        raise UnknownScheduleType()

    return run_query_across_partitioned_databases(ScheduleInstance, schedule_filter)
