import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.reminders.tasks import case_changed
from dimagi.utils.logging import notify_exception

def case_changed_receiver(sender, case, **kwargs):
    try:
        handler_ids = CaseReminderHandler.get_handlers(case.domain,
            ids_only=True)
        if len(handler_ids) > 0:
            case_changed.delay(case._id, handler_ids)
    except Exception:
        notify_exception(None,
            message="Error in reminders case changed receiver for case %s" %
            case._id)

case_post_save.connect(case_changed_receiver, CommCareCase)

