from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save

from corehq.apps.data_interfaces.models import AUTO_UPDATE_XMLNS
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import AUTO_CASE_UPDATE_ENHANCEMENTS
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save


def case_changed_receiver(sender, case, **kwargs):
    """
    Spawns a task to run auto update rules tied to the given case.
    """
    from corehq.apps.data_interfaces.tasks import run_case_update_rules_on_save

    if FormAccessors(case.domain).get_form(case.xform_ids[-1]).xmlns != AUTO_UPDATE_XMLNS \
            and AUTO_CASE_UPDATE_ENHANCEMENTS.enabled(case.domain):
        run_case_update_rules_on_save.delay(case.domain, case.type, case.case_id)


case_post_save.connect(case_changed_receiver, CommCareCase)
sql_case_post_save.connect(case_changed_receiver, CommCareCaseSQL)