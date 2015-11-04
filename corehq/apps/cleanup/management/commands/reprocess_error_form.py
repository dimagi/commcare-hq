import datetime
import warnings
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.xform import get_and_check_xform_domain, CaseDbCache, process_cases_with_casedb
from couchforms.models import XFormError, XFormInstance


def _process_cases(xform, config=None):
    """
    Creates or updates case objects which live outside of the form.

    If reconcile is true it will perform an additional step of
    reconciling the case update history after the case is processed.
    """
    warnings.warn(
        'This function is deprecated. You should be using SubmissionPost.',
        DeprecationWarning,
    )

    assert getattr(settings, 'UNIT_TESTING', False)
    domain = get_and_check_xform_domain(xform)

    with CaseDbCache(domain=domain, lock=True, deleted_ok=True) as case_db:
        case_result = process_cases_with_casedb([xform], case_db, config=config)

    cases = case_result.cases
    docs = [xform] + cases
    now = datetime.datetime.utcnow()
    for case in cases:
        case.server_modified_on = now
    XFormInstance.get_db().bulk_save(docs)

    for case in cases:
        case_post_save.send(CommCareCase, case=case)

    case_result.commit_dirtiness_flags()
    return cases


def reprocess_form_cases(form):
    """
    For a given form, reprocess all case elements inside it. This operation
    should be a no-op if the form was sucessfully processed, but should
    correctly inject the update into the case history if the form was NOT
    successfully processed.
    """
    _process_cases(form)
    # mark cleaned up now that we've reprocessed it
    if form.doc_type != 'XFormInstance':
        form = XFormInstance.get(form._id)
        form.doc_type = 'XFormInstance'
        form.save()


class Command(BaseCommand):
    args = '<id>'
    help = ('Reprocesses a single form, by ID.')

    def handle(self, *args, **options):
        if len(args) == 1:
            id = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        reprocess_form_cases(XFormError.get(id))
