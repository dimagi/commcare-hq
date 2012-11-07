from django.core.management.base import LabelCommand
import sys
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance

class Command(LabelCommand):
    help = "Recalculate sms rates for a particular month."
    args = "<year, ex: 2012> <month integer: 1-12> <optional: domain>"
    label = ""

    def handle(self, *args, **options):
        test_forms = XFormInstance.view('reports/all_submissions',
            reduce=False,
            startkey=["hsph"],
            endkey=["hsph", "2012-11-07"],
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

