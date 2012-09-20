from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import CaseReminderHandler, CASE_CRITERIA

def case_changed_receiver(sender, case, **kwargs):
    handlers = CaseReminderHandler.get_handlers(case.domain)
    for handler in handlers:
        if handler.start_condition_type == CASE_CRITERIA:
            handler.case_changed(case)
    
case_post_save.connect(case_changed_receiver, CommCareCase)

