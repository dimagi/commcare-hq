import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.reminders.tasks import case_changed

def case_changed_receiver(sender, case, **kwargs):
    handler_ids = CaseReminderHandler.get_handlers(case.domain, ids_only=True)
    if len(handler_ids) > 0:
        case_changed.delay(case._id, handler_ids)

case_post_save.connect(case_changed_receiver, CommCareCase)

