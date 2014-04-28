from casexml.apps.case.signals import cases_received
from custom.m4change.constants import M4CHANGE_DOMAINS, ALL_M4CHANGE_FORMS


def handle_form_duplicates(sender, xform, cases, **kwargs):
    if hasattr(xform, "domain") and xform.domain in M4CHANGE_DOMAINS\
            and hasattr(xform, "xmlns") and xform.xmlns in ALL_M4CHANGE_FORMS:
        for case in cases:
            forms = case.get_forms()
            for form in forms:
                if xform.xmlns == form.xmlns and xform._id != form._id and\
                                xform.received_on.date() == form.received_on.date():
                    xform.archive()
                    return


cases_received.connect(handle_form_duplicates)
