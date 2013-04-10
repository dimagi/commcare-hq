from django.dispatch.dispatcher import Signal
from receiver.signals import successful_form_received
from casexml.apps.phone.models import SyncLog
from dimagi.utils.decorators.log_exception import log_exception

class CaseProcessingConfig(object):
    def __init__(self, reconcile=False, strict_asserts=True, failing_case_ids=None):
        self.reconcile = reconcile
        self.strict_asserts = strict_asserts
        self.failing_case_ids = failing_case_ids or []

    def __repr__(self):
        return 'reconcile: {reconcile}, strict: {strict}, ids: {ids}'.format(
            reconcile=self.reconcile,
            strict=self.strict_asserts,
            ids=", ".join(self.failing_case_ids)
        )

@log_exception()
def process_cases(sender, xform, config=None, **kwargs):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """
    # recursive import fail
    config = config or CaseProcessingConfig()
    from casexml.apps.case.xform import get_or_update_cases
    cases = get_or_update_cases(xform).values()

    if config.reconcile:
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
        relevant_log.strict = config.strict_asserts
        from casexml.apps.case.util import update_sync_log_with_checks
        update_sync_log_with_checks(relevant_log, xform, cases,
                                    failing_case_ids=config.failing_case_ids)

        if config.reconcile:
            relevant_log.reconcile_cases()
            relevant_log.save()

    # set flags for indicator pillows and save
    xform.initial_processing_complete = True

    # if there are pillows or other _changes listeners competing to update
    # this form, override them. this will create a new entry in the feed
    # that they can re-pick up on
    xform.save(force_update=True)
    for case in cases:
        case.force_save()


successful_form_received.connect(process_cases)

case_post_save = Signal(providing_args=["case"])
