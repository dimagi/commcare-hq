from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.toggles import RUN_AUTO_CASE_UPDATES_ON_SAVE
from dimagi.utils.logging import notify_exception


def case_changed_receiver(sender, case, **kwargs):
    """
    Spawns a task to run auto update rules tied to the given case.
    """
    try:
        from corehq.apps.data_interfaces.tasks import run_case_update_rules_on_save

        if RUN_AUTO_CASE_UPDATES_ON_SAVE.enabled(case.domain):
            run_case_update_rules_on_save.delay(case)
    except Exception as e:
        error_message = 'Exception in case update signal'
        notify_exception(None, "{msg}: {exc}".format(msg=error_message, exc=e))
