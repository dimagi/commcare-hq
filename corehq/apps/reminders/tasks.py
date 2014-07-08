from datetime import timedelta
from celery.task import periodic_task, task
from corehq.apps.reminders.models import CaseReminderHandler, CASE_CRITERIA
from django.conf import settings
from dimagi.utils.logging import notify_exception
from casexml.apps.case.models import CommCareCase

@periodic_task(run_every=timedelta(minutes=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def fire_reminders():
    CaseReminderHandler.fire_reminders()

def get_subcases(case):
    indices = case.reverse_indices
    subcases = []
    for index in indices:
        if index.identifier == "parent":
            subcases.append(CommCareCase.get(index.referenced_id))
    return subcases

@task
def case_changed(case_id, handler_ids):
    try:
        _case_changed(case_id, handler_ids)
    except Exception:
        notify_exception(None,
            message="Error processing reminder rule updates for case %s" %
            case_id)

def _case_changed(case_id, handler_ids):
    subcases = None
    case = CommCareCase.get(case_id)
    for handler_id in handler_ids:
        handler = CaseReminderHandler.get(handler_id)
        if handler.start_condition_type == CASE_CRITERIA:
            handler.case_changed(case)
            if handler.uses_parent_case_property:
                if subcases is None:
                    subcases = get_subcases(case)
                for subcase in subcases:
                    handler.case_changed(subcase)

@task(queue=settings.CELERY_REMINDER_RULE_QUEUE)
def process_reminder_rule(handler, schedule_changed, prev_definition,
    send_immediately):
    try:
        handler.process_rule(schedule_changed, prev_definition, send_immediately)
    except Exception:
        notify_exception(None,
            message="Error processing reminder rule for handler %s" % handler._id)
    handler.save(unlock=True)

