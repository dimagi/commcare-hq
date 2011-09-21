from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import CaseReminderHandler

def case_changed_receiver(sender, case, **kwargs):
    handlers = CaseReminderHandler.get_handlers(case.domain, case.type)
    for handler in handlers:
        handler.case_changed(case)
    
case_post_save.connect(case_changed_receiver, CommCareCase)