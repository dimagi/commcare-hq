from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import (CaseReminderHandler,
    REMINDER_TYPE_DEFAULT)
from corehq.apps.reminders.tasks import case_changed
from dimagi.utils.logging import notify_exception

def case_changed_receiver(sender, case, **kwargs):
    """
    Fires reminders associated with the case, if any exist.
    """
    try:
        handler_ids = CaseReminderHandler.get_handler_ids(case.domain,
            reminder_type_filter=REMINDER_TYPE_DEFAULT)
        if len(handler_ids) > 0:
            case_changed.delay(case._id, handler_ids)
    except Exception:
        notify_exception(None,
            message="Error in reminders case changed receiver for case %s" %
            case._id)

case_post_save.connect(case_changed_receiver, CommCareCase)

