from corehq.toggles import AUTO_CASE_UPDATE_ENHANCEMENTS
from dimagi.utils.logging import notify_exception


def case_changed_receiver(sender, case, **kwargs):
    """
    Spawns a task to run auto update rules tied to the given case.
    """
    try:
        from corehq.apps.data_interfaces.tasks import run_case_update_rules_on_save

        if AUTO_CASE_UPDATE_ENHANCEMENTS.enabled(case.domain):
            run_case_update_rules_on_save.delay(case)
    except Exception as e:
        error_message = 'Exception in case update signal'
        notify_exception(None, u"{msg}: {exc}".format(msg=error_message, exc=e))
