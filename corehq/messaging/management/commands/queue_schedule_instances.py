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
from corehq.toggles import DATA_MIGRATION
from datetime import datetime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.logging import notify_exception
from django.core.management.base import BaseCommand
from time import sleep


class Command(BaseCommand):
    args = ""
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

    def get_enqueue_lock(self, cls, schedule_instance_id):
        client = get_redis_client()
        key = "create-task-for-%s-%s" % (cls.__name__, schedule_instance_id.hex)
        return client.lock(key, timeout=60 * 60)

    def create_tasks(self):
        for cls in (AlertScheduleInstance, TimedScheduleInstance):
            for domain, schedule_instance_id in get_active_schedule_instance_ids(cls, datetime.utcnow()):
                if DATA_MIGRATION.enabled(domain):
                    return

                enqueue_lock = self.get_enqueue_lock(cls, schedule_instance_id)
                if enqueue_lock.acquire(blocking=False):
                    self.get_task(cls).delay(schedule_instance_id, enqueue_lock)

        for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
            for domain, case_id, schedule_instance_id in get_active_case_schedule_instance_ids(cls, datetime.utcnow()):
                if DATA_MIGRATION.enabled(domain):
                    return

                enqueue_lock = self.get_enqueue_lock(cls, schedule_instance_id)
                if enqueue_lock.acquire(blocking=False):
                    self.get_task(cls).delay(case_id, schedule_instance_id, enqueue_lock)

    def handle(self, **options):
        while True:
            try:
                self.create_tasks()
            except:
                notify_exception(None, message="Could not fetch due reminders")
            sleep(10)
