from corehq.form_processor.models import FormArchiveRebuild
from couchforms.signals import xform_archived, xform_unarchived


def rebuild_form_cases(sender, xform, *args, **kwargs):
    from casexml.apps.case.xform import get_case_ids_from_form
    from casexml.apps.case.cleanup import rebuild_case_from_forms

    domain = xform.domain
    case_ids = get_case_ids_from_form(xform)
    detail = FormArchiveRebuild(xmlns=xform.xmlns, form_id=xform.form_id, archived=xform.is_archived)
    for case_id in case_ids:
        rebuild_case_from_forms(domain, case_id, detail)


_connected = False


def connect_signals():
    global _connected
    if _connected:
        return
    xform_archived.connect(rebuild_form_cases)
    xform_unarchived.connect(rebuild_form_cases)
    _connected = True
