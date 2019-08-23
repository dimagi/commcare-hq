from __future__ import absolute_import, unicode_literals

from uuid import UUID

from django.db.models import Q

from corehq.sql_db.util import (
    get_db_aliases_for_partitioned_query,
    paginate_query_across_partitioned_databases,
)
from corehq.util.datadog.utils import load_counter_for_model


def _validate_class(obj, cls):
    """
    :param cls: A type or tuple of types to check the type of obj against
    """
    if not isinstance(obj, cls):
        raise TypeError("Expected an instance of %s" % str(cls))


def _validate_uuid(value):
    _validate_class(value, UUID)


def get_alert_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_uuid(schedule_instance_id)
    return AlertScheduleInstance.objects.partitioned_get(schedule_instance_id)


def get_timed_schedule_instance(schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_uuid(schedule_instance_id)
    return TimedScheduleInstance.objects.partitioned_get(schedule_instance_id)


def save_alert_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(instance, AlertScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    instance.save()


def save_timed_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(instance, TimedScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    instance.save()


def delete_alert_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(instance, AlertScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    instance.delete()


def delete_timed_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(instance, TimedScheduleInstance)
    _validate_uuid(instance.schedule_instance_id)
    instance.delete()


def get_count_of_active_schedule_instances_due(domain, due_before):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance,
        TimedScheduleInstance,
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    classes = (AlertScheduleInstance, TimedScheduleInstance, CaseAlertScheduleInstance, CaseTimedScheduleInstance)

    result = 0

    for db_alias in get_db_aliases_for_partitioned_query():
        for cls in classes:
            result += cls.objects.using(db_alias).filter(
                domain=domain,
                active=True,
                next_event_due__lt=due_before
            ).count()

    return result


def get_active_schedule_instance_ids(cls, due_before, due_after=None):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance,
        TimedScheduleInstance,
    )

    if cls not in (AlertScheduleInstance, TimedScheduleInstance):
        raise TypeError("Expected AlertScheduleInstance or TimedScheduleInstance")

    active_filter = Q(
        active=True,
        next_event_due__lte=due_before,
    )

    if due_after:
        if due_before <= due_after:
            raise ValueError("Expected due_before > due_after")
        active_filter = active_filter & Q(next_event_due__gt=due_after)

    for domain, schedule_instance_id, next_event_due in paginate_query_across_partitioned_databases(
        cls,
        active_filter,
        values=['domain', 'schedule_instance_id', 'next_event_due'],
        load_source='get_schedule_instance_ids'
    ):
        yield domain, schedule_instance_id, next_event_due


def get_active_case_schedule_instance_ids(cls, due_before, due_after=None):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    if cls not in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
        raise TypeError("Expected CaseAlertScheduleInstance or CaseTimedScheduleInstance")

    active_filter = Q(
        active=True,
        next_event_due__lte=due_before,
    )

    if due_after:
        if due_before <= due_after:
            raise ValueError("Expected due_before > due_after")
        active_filter = active_filter & Q(next_event_due__gt=due_after)

    for domain, case_id, schedule_instance_id, next_event_due in _paginate_query_across_partitioned_databases(
        cls,
        active_filter,
        load_source='get_schedule_instance_ids'
    ):
        yield (domain, case_id, schedule_instance_id, next_event_due)


def _paginate_query_across_partitioned_databases(model_class, q_expression, load_source):
    """Optimized version of the generic paginate_query_across_partitioned_databases for case schedules

    queue_schedule_instances uses a lock to ensure that the same case_id cannot be queued within one
    hour of another instance
    The celery tasks handle_case_alert_schedule_instance and handle_case_timed_schedule_instance both
    use locks to ensure only one taks is operating on a case at one time. Each task also checks if the
    schedule is still valid on this case before processing it further

    Assumes that q_expression includes active = True
    """
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    if model_class not in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
        raise TypeError("Expected CaseAlertScheduleInstance or CaseTimedScheduleInstance")

    db_names = get_db_aliases_for_partitioned_query()
    for db_name in db_names:
        for row in _paginate_query(db_name, model_class, q_expression, load_source):
            yield row


def _paginate_query(db_name, model_class, q_expression, load_source, query_size=5000):
    track_load = load_counter_for_model(model_class)(load_source, None, extra_tags=['db:{}'.format(db_name)])
    sort_cols = ('active', 'next_event_due')

    # active is always set to true in the queryset's q_expression so we
    # don't need to include it here or filter it further later
    return_values = ['pk', 'domain', 'case_id', 'schedule_instance_id', 'next_event_due']

    qs = (
        model_class.objects.using(db_name)
        .filter(q_expression)
        .order_by(*sort_cols)
        .values_list(*return_values)
    )

    filter_expression = {}
    previous_pks = set()
    while True:
        current_pks = set()
        last_row = None
        results = qs.filter(**filter_expression)[:query_size]

        for row in results:
            track_load()

            current_pks.add(row[0])
            if row[0] in previous_pks:
                continue

            yield row[1:]
            last_row = row

        if len(results) < query_size:
            break

        if last_row is None:
            # This iteration produced the same result set as last time
            # likely because the next_event_due is the same for > query_size records
            # break here because the next iteration of this code should pick up
            # these instances once already queued instances have been processed
            break

        # Use gte here because its not guaranteed to have completed the final
        # events that are due on this instance for the same time
        filter_expression = {
            'next_event_due__gte': last_row[4]
        }
        previous_pks = current_pks


def get_alert_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import AlertSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(schedule, AlertSchedule)
    return paginate_query_across_partitioned_databases(
        AlertScheduleInstance,
        Q(alert_schedule_id=schedule.schedule_id),
        load_source='schedule_instances_for_schedule'
    )


def get_timed_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import TimedSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(schedule, TimedSchedule)
    return paginate_query_across_partitioned_databases(
        TimedScheduleInstance,
        Q(timed_schedule_id=schedule.schedule_id),
        load_source='schedule_instances_for_schedule'
    )


def get_case_alert_schedule_instances_for_schedule_id(case_id, schedule_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import CaseAlertScheduleInstance
    return CaseAlertScheduleInstance.objects.partitioned_query(case_id).filter(
        case_id=case_id,
        alert_schedule_id=schedule_id
    )


def get_case_timed_schedule_instances_for_schedule_id(case_id, schedule_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
    return CaseTimedScheduleInstance.objects.partitioned_query(case_id).filter(
        case_id=case_id,
        timed_schedule_id=schedule_id
    )


def get_case_alert_schedule_instances_for_schedule(case_id, schedule):
    from corehq.messaging.scheduling.models import AlertSchedule

    _validate_class(schedule, AlertSchedule)
    return get_case_alert_schedule_instances_for_schedule_id(case_id, schedule.schedule_id)


def get_case_timed_schedule_instances_for_schedule(case_id, schedule):
    from corehq.messaging.scheduling.models import TimedSchedule

    _validate_class(schedule, TimedSchedule)
    return get_case_timed_schedule_instances_for_schedule_id(case_id, schedule.schedule_id)


def get_case_schedule_instance(cls, case_id, schedule_instance_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    if cls not in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
        raise TypeError("Expected CaseAlertScheduleInstance or CaseTimedScheduleInstance")

    _validate_uuid(schedule_instance_id)
    return cls.objects.partitioned_get(case_id, schedule_instance_id=schedule_instance_id)


def save_case_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    _validate_class(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance))
    _validate_uuid(instance.schedule_instance_id)
    instance.save()


def delete_case_schedule_instance(instance):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
    )

    _validate_class(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance))
    instance.delete()


def delete_alert_schedule_instances_for_schedule(cls, schedule_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance,
        CaseAlertScheduleInstance,
    )

    if cls not in (AlertScheduleInstance, CaseAlertScheduleInstance):
        raise TypeError("Expected AlertScheduleInstance or CaseAlertScheduleInstance")

    _validate_uuid(schedule_id)

    for db_name in get_db_aliases_for_partitioned_query():
        cls.objects.using(db_name).filter(alert_schedule_id=schedule_id).delete()


def delete_timed_schedule_instances_for_schedule(cls, schedule_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        TimedScheduleInstance,
        CaseTimedScheduleInstance,
    )

    if cls not in (TimedScheduleInstance, CaseTimedScheduleInstance):
        raise TypeError("Expected TimedScheduleInstance or CaseTimedScheduleInstance")

    _validate_uuid(schedule_id)

    for db_name in get_db_aliases_for_partitioned_query():
        cls.objects.using(db_name).filter(timed_schedule_id=schedule_id).delete()


def delete_schedule_instances_by_case_id(domain, case_id):
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        CaseTimedScheduleInstance,
        CaseAlertScheduleInstance,
    )

    for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
        for db_name in get_db_aliases_for_partitioned_query():
            cls.objects.using(db_name).filter(domain=domain, case_id=case_id).delete()
