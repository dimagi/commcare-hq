from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.sql_db.util import (
    paginate_query_across_partitioned_databases,
    run_query_across_partitioned_databases,
    get_db_aliases_for_partitioned_query,
)
from django.db.models import Q
from uuid import UUID


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

    for domain, schedule_instance_id, next_event_due in run_query_across_partitioned_databases(
        cls,
        active_filter,
        values=['domain', 'schedule_instance_id', 'next_event_due']
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

    for domain, case_id, schedule_instance_id, next_event_due in run_query_across_partitioned_databases(
        cls,
        active_filter,
        values=['domain', 'case_id', 'schedule_instance_id', 'next_event_due']
    ):
        yield (domain, case_id, schedule_instance_id, next_event_due)


def get_alert_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import AlertSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import AlertScheduleInstance

    _validate_class(schedule, AlertSchedule)
    return paginate_query_across_partitioned_databases(
        AlertScheduleInstance,
        Q(alert_schedule_id=schedule.schedule_id)
    )


def get_timed_schedule_instances_for_schedule(schedule):
    from corehq.messaging.scheduling.models import TimedSchedule
    from corehq.messaging.scheduling.scheduling_partitioned.models import TimedScheduleInstance

    _validate_class(schedule, TimedSchedule)
    return paginate_query_across_partitioned_databases(
        TimedScheduleInstance,
        Q(timed_schedule_id=schedule.schedule_id)
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
