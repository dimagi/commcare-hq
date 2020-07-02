from datetime import datetime
from time import sleep

from django.core.management.base import BaseCommand

from corehq import toggles
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.logging import notify_exception

from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.smsforms.models import SQLXFormsSession, XFormsSessionSynchronization
from corehq.apps.smsforms.tasks import handle_due_survey_action
from corehq.sql_db.util import handle_connection_failure


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
    help = "Spawns tasks to handle the next actions due in SMS surveys"

    @staticmethod
    def get_enqueue_lock(session_id, current_action_due):
        key = "create-task-for-smsforms-session-%s-%s" % (
            session_id,
            current_action_due.strftime('%Y-%m-%d %H:%M:%S')
        )
        return get_redis_lock(
            key,
            timeout=60 * 60,
            name="smsforms_task",
            track_unreleased=False,
        )

    def get_survey_sessions_due_for_action(self):
        return SQLXFormsSession.objects.filter(
            session_is_open=True,
            current_action_due__lt=datetime.utcnow(),
        ).values_list('domain', 'connection_id', 'session_id', 'current_action_due', 'phone_number')

    def get_open_session_ids(self):
        return SQLXFormsSession.objects.filter(
            session_is_open=True
        ).values_list('session_id', flat=True)

    @handle_connection_failure()
    def create_tasks(self):
        survey_sessions_due_for_action = self.get_survey_sessions_due_for_action()
        all_open_session_ids = self.get_open_session_ids()
        for domain, connection_id, session_id, current_action_due, phone_number in survey_sessions_due_for_action:
            if skip_domain(domain):
                continue

            if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(domain):
                fake_session = SQLXFormsSession(
                    session_id=session_id,
                    connection_id=connection_id,
                    phone_number=phone_number,
                )
                if not XFormsSessionSynchronization.channel_is_available_for_session(fake_session):
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
