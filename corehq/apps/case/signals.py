from receiver.signals import successful_form_received

def process_cases(sender, xform, **kwargs):
    """Creates or updates case objects which live outside of the form"""
    # recursive import fail
    from corehq.apps.case.xform import get_or_update_cases
    cases = get_or_update_cases(xform)
    # attach domain if it's there
    if hasattr(xform, "domain"):
        domain = xform.domain
        def attach_domain(case):
            case.domain = domain
            return case
        cases = [attach_domain(case) for case in cases]
    map(lambda pair: pair[1].save(), cases.items())
    
successful_form_received.connect(process_cases)