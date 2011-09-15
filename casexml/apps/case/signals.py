from django.dispatch.dispatcher import Signal
from receiver.signals import successful_form_received

def process_cases(sender, xform, **kwargs):
    """Creates or updates case objects which live outside of the form"""
    # recursive import fail
    from casexml.apps.case.xform import get_or_update_cases
    cases = get_or_update_cases(xform).values()
    # attach domain if it's there
    if hasattr(xform, "domain"):
        domain = xform.domain
        def attach_domain(case):
            case.domain = domain
            return case
        cases = [attach_domain(case) for case in cases]
    map(lambda case: case.save(), cases)
    
successful_form_received.connect(process_cases)

case_post_save = Signal(providing_args=["case"])