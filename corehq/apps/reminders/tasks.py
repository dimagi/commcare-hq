from datetime import datetime, timedelta
from celery.task import periodic_task, task
from corehq.apps.reminders.models import (CaseReminderHandler, CaseReminder,
    CASE_CRITERIA, REMINDER_TYPE_DEFAULT)
from django.conf import settings
from dimagi.utils.logging import notify_exception
from casexml.apps.case.models import CommCareCase
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.bulk import soft_delete_docs
from dimagi.utils.rate_limit import DomainRateLimiter


reminder_rate_limiter = DomainRateLimiter(
    'process-reminder-for-',
    settings.REMINDERS_RATE_LIMIT_COUNT,
    settings.REMINDERS_RATE_LIMIT_PERIOD
)


# In minutes
CASE_CHANGED_RETRY_INTERVAL = 5
CASE_CHANGED_RETRY_MAX = 10
CELERY_REMINDERS_QUEUE = "reminder_queue"


if not settings.REMINDERS_QUEUE_ENABLED:
    @periodic_task(run_every=timedelta(minutes=1),
        queue=settings.CELERY_PERIODIC_QUEUE)
    def fire_reminders():
        CaseReminderHandler.fire_reminders()


def get_subcases(case):
    indices = case.reverse_indices
    subcases = []
    for index in indices:
        if index.identifier == "parent":
            subcases.append(CommCareCase.get(index.referenced_id))
    return subcases


@task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, ignore_result=True, acks_late=True,
      default_retry_delay=CASE_CHANGED_RETRY_INTERVAL * 60, max_retries=CASE_CHANGED_RETRY_MAX,
      bind=True)
def case_changed(self, domain, case_id):
    try:
        handler_ids = CaseReminderHandler.get_handler_ids(
            domain,
            reminder_type_filter=REMINDER_TYPE_DEFAULT
        )
        if handler_ids:
            _case_changed(case_id, handler_ids)
    except Exception as e:
        self.retry(exc=e)


def _case_changed(case_id, handler_ids):
    subcases = None
    case = CommCareCase.get(case_id)
    for handler in CaseReminderHandler.get_handlers_from_ids(handler_ids):
        if handler.start_condition_type == CASE_CRITERIA:
            kwargs = {}
            if handler.uses_time_case_property:
                kwargs = {
                    'schedule_changed': True,
                    'prev_definition': handler,
                }
            handler.case_changed(case, **kwargs)
            if handler.uses_parent_case_property:
                if subcases is None:
                    subcases = get_subcases(case)
                for subcase in subcases:
                    handler.case_changed(subcase, **kwargs)


@task(queue=settings.CELERY_REMINDER_RULE_QUEUE, ignore_result=True, acks_late=True)
def process_reminder_rule(handler, schedule_changed, prev_definition,
    send_immediately):
    try:
        handler.process_rule(schedule_changed, prev_definition, send_immediately)
    except Exception:
        notify_exception(None,
            message="Error processing reminder rule for handler %s" % handler._id)
    handler.save(unlock=True)


@task(queue=CELERY_REMINDERS_QUEUE, ignore_result=True, acks_late=True)
def fire_reminder(reminder_id, domain):
    try:
        if reminder_rate_limiter.can_perform_action(domain):
            _fire_reminder(reminder_id)
        else:
            fire_reminder.apply_async(args=[reminder_id, domain], countdown=60)
    except Exception:
        notify_exception(None,
            message="Error firing reminder %s" % reminder_id)


def reminder_is_stale(reminder, utcnow):
    delta = timedelta(hours=settings.REMINDERS_QUEUE_STALE_REMINDER_DURATION)
    return (utcnow - delta) > reminder.next_fire


def _fire_reminder(reminder_id):
    utcnow = datetime.utcnow()
    reminder = CaseReminder.get(reminder_id)
    # This key prevents doc update conflicts with rule running
    key = "rule-update-definition-%s-case-%s" % (reminder.handler_id, reminder.case_id)
    with CriticalSection([key],
        timeout=(settings.REMINDERS_QUEUE_PROCESSING_LOCK_TIMEOUT*60)):
        # Refresh the reminder
        reminder = CaseReminder.get(reminder_id)
        if (not reminder.retired and reminder.active
            and utcnow >= reminder.next_fire):
            handler = reminder.handler
            if reminder_is_stale(reminder, utcnow):
                handler.set_next_fire(reminder, utcnow)
                reminder.save()
                return
            if handler.fire(reminder):
                handler.set_next_fire(reminder, utcnow)
                reminder.save()


@task(queue='background_queue', ignore_result=True, acks_late=True)
def delete_reminders_for_cases(domain, case_ids):
    handler_ids = CaseReminderHandler.get_handler_ids(
        domain, reminder_type_filter=REMINDER_TYPE_DEFAULT)
    for ids in chunked(case_ids, 50):
        keys = [[domain, handler_id, case_id]
                for handler_id in handler_ids
                for case_id in ids]
        results = CaseReminder.get_db().view(
            'reminders/by_domain_handler_case',
            keys=keys,
            include_docs=True
        )
        soft_delete_docs([row['doc'] for row in results], CaseReminder)
