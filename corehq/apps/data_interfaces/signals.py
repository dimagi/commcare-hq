from corehq.apps.data_interfaces.models import AUTO_UPDATE_XMLNS
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import AUTO_CASE_UPDATE_ENHANCEMENTS


def _spawn_task(case):
    if not AUTO_CASE_UPDATE_ENHANCEMENTS.enabled(case.domain):
        return False
    elif not case.xform_ids:
        return True
    else:
        last_form = FormAccessors(case.domain).get_form(case.xform_ids[-1])
        return last_form.xmlns != AUTO_UPDATE_XMLNS


def case_changed_receiver(sender, case, **kwargs):
    """
    Spawns a task to run auto update rules tied to the given case.
    """
    from corehq.apps.data_interfaces.tasks import run_case_update_rules_on_save

    if _spawn_task(case):
        run_case_update_rules_on_save.delay(case.domain, case.type, case.case_id)
