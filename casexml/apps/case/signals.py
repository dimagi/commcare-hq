from django.dispatch.dispatcher import Signal
from receiver.signals import successful_form_received
from casexml.apps.phone.models import SyncLog

def process_cases(sender, xform, **kwargs):
    """Creates or updates case objects which live outside of the form"""
    # recursive import fail
    from casexml.apps.case.xform import get_or_update_cases
    # avoid Document conflicts
    cases = get_or_update_cases(xform).values()
    # attach domain if it's there
    if hasattr(xform, "domain"):
        domain = xform.domain
        def attach_domain(case):
            case.domain = domain
            if domain and hasattr(case, 'type'):
                case['#export_tag'] = ["domain", "type"]
            return case
        cases = [attach_domain(case) for case in cases]
    
    map(lambda case: case.save(), cases)
    
    # HACK -- figure out how to do this more properly
    # todo: create a pillow for this
    if cases:
        case = cases[0]
        if case.location_ is not None:
            # should probably store this in computed_
            # re-fetch the xform to avoid document update conflicts
            from couchforms.models import XFormInstance
            xform_new = XFormInstance.get(xform._id)
            xform_new.location_ = list(case.location_)
            xform_new.save()

    # handle updating the sync records for apps that use sync mode
    if hasattr(xform, "last_sync_token") and xform.last_sync_token:
        relevant_log = SyncLog.get(xform.last_sync_token)
        relevant_log.update_phone_lists(xform, cases)
        
    
successful_form_received.connect(process_cases)

case_post_save = Signal(providing_args=["case"])
