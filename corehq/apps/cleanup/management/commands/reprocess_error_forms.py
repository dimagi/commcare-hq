import datetime
import warnings

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.xform import get_and_check_xform_domain, process_cases_with_casedb
from collections import defaultdict
from couchforms.models import XFormInstance
from dimagi.utils.parsing import string_to_datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, LabelCommand
from optparse import make_option

from corehq.apps.cleanup.xforms import iter_problem_forms
from corehq.form_processor.backends.couch.casedb import CaseDbCacheCouch


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

    with CaseDbCacheCouch(domain=domain, lock=True, deleted_ok=True) as case_db:
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
    args = '<domain> <since>'
    help = ('Reprocesses all documents tagged as errors and tries to '
            'regenerate the appropriate case blocks for them. Can pass in '
            'a domain and date to process forms received after that date or '
            'just a domain to process all problem forms in the domain.')
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual reprocessing, just print the ids that would be affected"),)

    def handle(self, *args, **options):
        domain = since = None
        if len(args) == 1:
            domain = args[0]
        elif len(args) == 2:
            domain = args[0]
            since = string_to_datetime(args[1])
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        succeeded = []
        failed = []
        error_messages = defaultdict(lambda: 0)
        for form in iter_problem_forms(domain, since):
            print "%s\t%s\t%s\t%s\t%s" % (form._id, form.received_on,
                              form.xmlns,
                              form.get_data('form/meta/username'),
                              form.problem.strip())
            if not options["dryrun"]:
                try:
                    reprocess_form_cases(form)
                except Exception, e:
                    failed.append(form._id)
                    error_messages[str(e)] += 1
                else:
                    succeeded.append(form._id)

        print "%s / %s forms successfully processed, %s failures" % \
              (len(succeeded), len(succeeded) + len(failed), len(failed))
        if error_messages:
            print "The following errors were seen: \n%s" % \
                  ("\n".join("%s: %s" % (v, k) for k, v in error_messages.items()))
