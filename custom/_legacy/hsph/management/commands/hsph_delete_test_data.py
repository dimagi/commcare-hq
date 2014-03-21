from django.core.management.base import LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.util import make_form_couch_key
from couchforms.models import XFormInstance

class Command(LabelCommand):
    help = "Recalculate sms rates for a particular month."
    args = "<year, ex: 2012> <month integer: 1-12> <optional: domain>"
    label = ""

    def handle(self, *args, **options):
        key = make_form_couch_key("hsph")
        test_forms = XFormInstance.view('reports_forms/all_forms',
            reduce=False,
            startkey=key,
            endkey=key+["2012-11-07"],
            include_docs=True,
        ).all()
        test_cases = CommCareCase.view('reports/case_activity',
            reduce=False,
            startkey=["","hsph"],
            endkey=["","hsph","2012-11-07"],
            include_docs=True,
        ).all()

        print "\nDELETING TEST HSPH FORMS"
        for form in test_forms:
            if form.domain == "hsph":
                sys.stdout.write(".")
                sys.stdout.flush()
                form.delete()

        print "\n\nDELETING TEST HSPH CASES"
        for case in test_cases:
            if case.domain == "hsph":
                sys.stdout.write(".")
                sys.stdout.flush()
                case.delete()
        print "\n"

