from django.core.management.base import BaseCommand

from corehq.util.argparse_types import date_type
from dimagi.utils.chunked import chunked

from corehq.apps.data_pipeline_audit.management.commands.compare_doc_ids import (
    compare_cases,
    compare_xforms,
)
from corehq.apps.hqcase.utils import resave_case
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.utils.xform import resave_form
from corehq.util.log import with_progress_bar

DATE_FORMAT = "%Y-%m-%d"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'start_date',
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )
        parser.add_argument(
            'end_date',
            type=date_type,
            help='The end date (exclusive). format YYYY-MM-DD'
        )
        parser.add_argument('--xforms', action='store_true')
        parser.add_argument('--cases', action='store_true')
        parser.add_argument('--no-input', action='store_true')

    def handle(self, domain, start_date, end_date, *args, **options):
        resave_xforms = options.get('xforms')
        resave_cases = options.get('cases')
        no_input = options.get('no_input', False)
        if resave_xforms:
            perform_resave_on_xforms(domain, start_date, end_date, no_input)
        if resave_cases:
            perform_resave_on_cases(domain, start_date, end_date, no_input)


def perform_resave_on_xforms(domain, start_date, end_date, no_input):
    _, _, xform_ids_missing_in_es, _ = compare_xforms(domain, 'XFormInstance', start_date, end_date)
    print("%s Ids found for xforms missing in ES." % len(xform_ids_missing_in_es))
    if len(xform_ids_missing_in_es) < 1000:
        print(xform_ids_missing_in_es)
    if no_input is not True:
        ok = input("Type 'ok' to continue: ")
        if ok != "ok":
            print("No changes made")
            return
    form_accessor = FormAccessors(domain)
    for xform_ids in chunked(with_progress_bar(xform_ids_missing_in_es), 100):
        xforms = form_accessor.get_forms(list(xform_ids))
        found_xform_ids = set()

        for xform in xforms:
            resave_form(domain, xform)
            found_xform_ids.add(xform.form_id)

        for xform_id in set(xform_ids) - found_xform_ids:
            print("form not found %s" % xform_id)


def perform_resave_on_cases(domain, start_date, end_date, no_input):
    _, _, case_ids_missing_in_es, _ = compare_cases(domain, 'CommCareCase', start_date, end_date)
    print("%s Ids found for cases missing in ES." % len(case_ids_missing_in_es))
    if len(case_ids_missing_in_es) < 1000:
        print(case_ids_missing_in_es)
    if no_input is not True:
        ok = input("Type 'ok' to continue: ")
        if ok != "ok":
            print("No changes made")
            return
    case_accessor = CaseAccessors(domain)
    for case_ids in chunked(with_progress_bar(case_ids_missing_in_es), 100):
        cases = case_accessor.get_cases(list(case_ids))
        found_case_ids = set()

        for case in cases:
            resave_case(domain, case, send_post_save_signal=False)
            found_case_ids.add(case.case_id)

        for case_id in set(case_ids) - found_case_ids:
            print("case not found %s" % case_id)
