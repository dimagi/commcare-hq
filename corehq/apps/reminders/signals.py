import logging
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.models import CaseReminderHandler, CASE_CRITERIA

def get_subcases(case):
    indices = case.reverse_indices
    subcases = []
    for index in indices:
        if index.identifier == "parent":
            subcases.append(CommCareCase.get(index.referenced_id))
    return subcases

def case_changed_receiver(sender, case, **kwargs):
    try:
        subcases = None
        handlers = CaseReminderHandler.get_handlers(case.domain)
        for handler in handlers:
            if handler.start_condition_type == CASE_CRITERIA:
                handler.case_changed(case)
                if handler.uses_parent_case_property:
                    if subcases is None:
                        subcases = get_subcases(case)
                    for subcase in subcases:
                        handler.case_changed(subcase)
    except Exception:
        logging.exception("Error processing reminders case_changed_receiver for case %s" % case._id)

case_post_save.connect(case_changed_receiver, CommCareCase)

