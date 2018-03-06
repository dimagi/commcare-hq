from __future__ import absolute_import
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.smsforms.tasks import handle_due_survey_action
from corehq.sql_db.util import handle_connection_failure
from datetime import datetime
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.logging import notify_exception
from django.core.management.base import BaseCommand
from time import sleep


def skip_domain(domain):
    return any_migrations_in_progress(domain)


class Command(BaseCommand):
    help = "Spawns tasks to handle the next actions due in SMS surveys"

    def get_enqueue_lock(self, session_id, current_action_due):
        client = get_redis_client()
        key = "create-task-for-smsforms-session-%s-%s" % (
            session_id,
            current_action_due.strftime('%Y-%m-%d %H:%M:%S')
        )
        return client.lock(key, timeout=60 * 60)

    def get_survey_sessions_due_for_action(self):
        return SQLXFormsSession.objects.filter(
            session_is_open=True,
            current_action_due__lt=datetime.utcnow(),
        ).values_list('domain', 'connection_id', 'session_id', 'current_action_due')

    @handle_connection_failure()
    def create_tasks(self):
        for domain, connection_id, session_id, current_action_due in self.get_survey_sessions_due_for_action():
            if skip_domain(domain):
                continue

            enqueue_lock = self.get_enqueue_lock(session_id, current_action_due)
            if enqueue_lock.acquire(blocking=False):
                handle_due_survey_action.delay(domain, connection_id, session_id)

    def handle(self, **options):
        while True:
            try:
                self.create_tasks()
            except:
                notify_exception(None, message="Could not fetch due survey actions")
            sleep(10)
