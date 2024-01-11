from attrs import define, field

from corehq.apps.hqwebapp.doc_info import get_case_url
from corehq.form_processor.models import XFormInstance


@define
class DeleteCase:
    name = field()
    url = field()
    is_primary = field(default=False)
    delete_forms = field(factory=list)


@define
class DeleteForm:
    name = field()
    url = field()
    affected_cases = field(factory=list)


@define
class FormAffectedCases:
    case_name = field(default=None)
    is_current_case = field(default=False)
    actions = field(factory=list)


@define
class AffectedCase:
    id = field()
    name = field()
    url = field()
    affected_forms = field(factory=list)


def get_affected_case(domain, case_id, case_name, affected_cases):
    for affected_case in affected_cases:
        if affected_case.id == case_id:
            return affected_case
    affected_case = AffectedCase(id=case_id, name=case_name, url=get_case_url(domain, case_id))
    affected_cases.append(affected_case)
    return affected_case


@define
class AffectedForm:
    name = field()
    url = field()
    actions = field()


@define
class ReopenedCase:
    name = field()
    url = field()
    closing_form = field()


def get_ordered_case_xforms(case, domain):
    # Returns deduplicated and chronologically ordered case xforms, if not already that
    xforms = [XFormInstance.objects.get_form(form_id, domain) for form_id in case.xform_ids]
    case_xforms = []
    for xform in xforms:
        if xform not in case_xforms:
            case_xforms.append(xform)
    case_xforms = sorted(case_xforms, key=lambda form: form.received_on)

    return case_xforms
