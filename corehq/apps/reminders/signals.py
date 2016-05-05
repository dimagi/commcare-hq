from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.reminders.tasks import case_changed
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save
from dimagi.utils.logging import notify_exception


def case_changed_receiver(sender, case, **kwargs):
    """
    Spawns a task to update reminder instances tied to the given case.
    """
    try:
        case_changed.delay(case.domain, case.case_id)
    except Exception:
        notify_exception(
            None,
            message="Could not create reminders case_changed task for case %s" % case.case_id
        )


case_post_save.connect(case_changed_receiver, CommCareCase)
sql_case_post_save.connect(case_changed_receiver, CommCareCaseSQL)
