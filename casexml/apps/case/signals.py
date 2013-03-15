from django.dispatch.dispatcher import Signal
from receiver.signals import successful_form_received
from casexml.apps.phone.models import SyncLog
from dimagi.utils.decorators.log_exception import log_exception
from couchforms.models import XFormInstance

@log_exception()
def process_cases(sender, xform, reconcile=False, **kwargs):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """
    # recursive import fail
    from casexml.apps.case.xform import get_or_update_cases
    cases = get_or_update_cases(xform).values()

    if reconcile:
        for c in cases:
            c.reconcile_actions(rebuild=True)

    # attach domain and export tag if domain is there
    if hasattr(xform, "domain"):
        domain = xform.domain
        def attach_extras(case):
            case.domain = domain
            if domain and hasattr(case, 'type'):
                case['#export_tag'] = ["domain", "type"]
            return case
        cases = [attach_extras(case) for case in cases]

    # HACK -- figure out how to do this more properly
    # todo: create a pillow for this
    if cases:
        case = cases[0]
        if case.location_ is not None:
            # should probably store this in computed_
            xform.location_ = list(case.location_)

    # handle updating the sync records for apps that use sync mode
    if hasattr(xform, "last_sync_token") and xform.last_sync_token:
        relevant_log = SyncLog.get(xform.last_sync_token)
        # in reconciliation mode, things can be unexpected
        relevant_log.strict = not reconcile
        relevant_log.update_phone_lists(xform, cases)
        if reconcile:
            relevant_log.reconcile_cases()
            relevant_log.save()

    # set flags for indicator pillows and save
    xform.initial_processing_complete = True

    # if there are pillows or other _changes listeners competing to update
    # this form, override them. this will create a new entry in the feed
    # that they can re-pick up on
    xform.save(force_update=True)
    for case in cases:
        case.save(force_update=True)


successful_form_received.connect(process_cases)

case_post_save = Signal(providing_args=["case"])
