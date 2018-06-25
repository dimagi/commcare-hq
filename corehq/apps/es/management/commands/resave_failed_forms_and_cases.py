from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from six.moves import input
from django.core.management.base import BaseCommand
from corehq.apps.data_pipeline_audit.management.commands.compare_doc_ids import (
    compare_xforms,
    compare_cases,
)
from corehq.form_processor.interfaces.dbaccessors import (
    FormAccessors,
    CaseAccessors,
)
from corehq.form_processor.utils.xform import resave_form
from corehq.apps.hqcase.utils import resave_case
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--xforms', action='store_true')
        parser.add_argument('--cases', action='store_true')

    def handle(self, domain, *args, **options):
        resave_xforms = options.get('xforms')
        resave_cases = options.get('cases')
        if resave_xforms:
            perform_resave_on_xforms(domain)
        if resave_cases:
            perform_resave_on_cases(domain)


def perform_resave_on_xforms(domain):
    xform_ids_missing_in_es, _ = compare_xforms(domain, 'XFormInstance')
    print("%s Ids found for xforms missing in ES." % len(xform_ids_missing_in_es))
    print(xform_ids_missing_in_es)
    ok = input("Type 'ok' to continue: ")
    if ok != "ok":
        print("No changes made")
        return
    form_accessor = FormAccessors(domain)
    for xform_ids in chunked(with_progress_bar(xform_ids_missing_in_es), 100):
        xforms = form_accessor.get_forms(xform_ids)
        found_xform_ids = set()

        for xform in xforms:
            resave_form(domain, xform)
            found_xform_ids.add(xform.form_id)

        for xform_id in xform_ids - found_xform_ids:
            print("form not found %s" % xform_id)


def perform_resave_on_cases(domain):
    case_ids_missing_in_es, _ = compare_cases(domain, 'CommCareCase')
    print("%s Ids found for cases missing in ES." % len(case_ids_missing_in_es))
    print(case_ids_missing_in_es)
    ok = input("Type 'ok' to continue: ")
    if ok != "ok":
        print("No changes made")
        return
    case_accessor = CaseAccessors(domain)
    for case_ids in chunked(with_progress_bar(case_ids_missing_in_es), 100):
        cases = case_accessor.get_cases(case_ids)
        found_case_ids = set()

        for case in cases:
            resave_case(domain, case, send_post_save_signal=False)
            found_case_ids.add(case.case_id)

        for case_id in case_ids - found_case_ids:
            print("case not found %s" % case_id)
