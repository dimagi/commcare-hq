from corehq.sql_db.util import (
    get_object_from_partitioned_database,
    save_object_to_partitioned_database,
    run_query_across_partitioned_databases,
)
from datetime import datetime
from django.db.models import Q


def get_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    return get_object_from_partitioned_database(ScheduleInstance, str(schedule_instance_id))


def save_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    if not isinstance(instance, ScheduleInstance):
        raise ValueError("Expected an instance of ScheduleInstance")

    save_object_to_partitioned_database(instance, str(instance.pk))


def delete_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    if not isinstance(instance, ScheduleInstance):
        raise ValueError("Expected an instance of ScheduleInstance")

    delete_object_from_partitioned_database(instance, str(instance.pk))


def get_active_schedule_instance_ids(start_timestamp, end_timestamp):
    from corehq.messaging.scheduling.scheduling_partitioned.models import ScheduleInstance

    q_expression = Q(
        active=True,
        next_event_due__gt=start_timestamp,
        next_event_due__lte=end_timestamp,
    )
    for schedule_instance_id in run_query_across_partitioned_databases(
        ScheduleInstance,
        q_expression,
        values=['schedule_instance_id']
    ):
        yield schedule_instance_id
