from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_active_schedule_instance_ids,
    get_active_case_schedule_instance_ids,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.tasks import (
    handle_alert_schedule_instance,
    handle_timed_schedule_instance,
    handle_case_alert_schedule_instance,
    handle_case_timed_schedule_instance,
)
from corehq.sql_db.util import handle_connection_failure, get_default_and_partitioned_db_aliases
from datetime import datetime
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.logging import notify_exception
from django.core.management.base import BaseCommand
from time import sleep


def skip_domain(domain):
    return any_migrations_in_progress(domain)


class Command(BaseCommand):
    """
    Based on our commcare-cloud code, there will be one instance of this
    command running on every machine that has a celery worker which
    consumes from the reminder_queue. This is ok because this process uses
    locks to ensure items are only enqueued once, and it's what is desired
    in order to more efficiently spawn the needed celery tasks.
    """
    help = "Spawns tasks to process schedule instances"

    def get_task(self, cls):
        task = {
            AlertScheduleInstance: handle_alert_schedule_instance,
            TimedScheduleInstance: handle_timed_schedule_instance,
            CaseAlertScheduleInstance: handle_case_alert_schedule_instance,
            CaseTimedScheduleInstance: handle_case_timed_schedule_instance,
        }.get(cls)

        if task:
            return task

        raise ValueError("Unexpected class: %s" % cls)

    def get_enqueue_lock(self, cls, schedule_instance_id, next_event_due):
        key = "create-task-for-%s-%s-%s" % (
            cls.__name__,
            schedule_instance_id.hex,
            next_event_due.strftime('%Y-%m-%d %H:%M:%S')
        )
        return get_redis_lock(
            key,
            timeout=60 * 60,
            name="create_task_for_%s" % cls.__name__,
            track_unreleased=False,
        )

    @handle_connection_failure(get_db_aliases=get_default_and_partitioned_db_aliases)
    def create_tasks(self):
        for cls in (AlertScheduleInstance, TimedScheduleInstance):
            for domain, schedule_instance_id, next_event_due in get_active_schedule_instance_ids(
                    cls, datetime.utcnow()):
                if skip_domain(domain):
                    continue

                # We use a non-blocking lock here with a timeout of one hour to make sure
                # that we only retry non-processed schedule instances once an hour.
                enqueue_lock = self.get_enqueue_lock(cls, schedule_instance_id, next_event_due)
                if enqueue_lock.acquire(blocking=False):
                    self.get_task(cls).delay(schedule_instance_id)

        for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
            for domain, case_id, schedule_instance_id, next_event_due in get_active_case_schedule_instance_ids(
                    cls, datetime.utcnow()):
                if skip_domain(domain):
                    continue

                # See comment above about why we use a non-blocking lock here.
                enqueue_lock = self.get_enqueue_lock(cls, schedule_instance_id, next_event_due)
                if enqueue_lock.acquire(blocking=False):
                    self.get_task(cls).delay(case_id, schedule_instance_id)

    def handle(self, **options):
        while True:
            try:
                self.create_tasks()
            except:
                notify_exception(None, message="Could not fetch due reminders")
            sleep(10)
