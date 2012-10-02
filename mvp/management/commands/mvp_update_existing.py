import logging
from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, DocumentMistmatchError, DocumentNotInDomainError
from couchforms.models import XFormInstance
from mvp.models import MVP, MVPCannotFetchCaseError

class Command(LabelCommand):
    help = "Update MVP indicators in existing cases and forms."
    args = ""
    label = ""

    def handle(self, *args, **options):
        print "Fetching all child visit forms..."
        all_child_visit_forms = XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A"
        ).all()
        print "Fetching all household visit forms..."
        all_household_visit_forms = XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key="http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B"
        ).all()
        all_forms = all_child_visit_forms + all_household_visit_forms

        total_form_count = 0
        for domain in MVP.DOMAINS:
            all_form_definitions = FormIndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=domain)
            form_count = 0
            for form in all_forms:
                indicator_count = 0
                for definition in all_form_definitions:
                    try:
                        form.set_definition(definition)
                        form.save()
                        indicator_count += 1
                    except ResourceNotFound:
                        print "ResourceNotFound triggered by form:", form.get_id
                    except DocumentMistmatchError:
                        pass
                    except MVPCannotFetchCaseError:
                        pass
                    except DocumentNotInDomainError:
                        pass
                print "SAVED %d indicators: FORM (%s) in domain %s." % (indicator_count, form.get_id, domain)
                form_count += 1 if (indicator_count > 0) else 0
            print "DONE. %d out %d forms in domain %s had indicators updated." % \
                    (form_count, len(all_forms), domain)
            total_form_count += form_count
        print "FORMS ALL DONE. %d forms processed." % total_form_count

        total_case_count = 0
        for domain in MVP.DOMAINS:
            key = ["all", domain]
            print "Fetching all cases for domain %s..." % domain
            all_cases = CommCareCase.view("case/all_cases",
                reduce=False,
                include_docs=True,
                startkey=key,
                endkey=key+[{}]
            ).all()
            all_case_definitions = CaseIndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=domain)
            case_count = 0
            for case in all_cases:
                indicator_count = 0
                for definition in all_case_definitions:
                    try:
                        case.set_definition(definition)
                        case.save()
                        print "SAVED Indicators for Case %s in domain %s." % (case.get_id, domain)
                        indicator_count += 1
                    except Exception:
                        pass
                print "SAVED %d indicators: CASE (%s) in domain %s." % (indicator_count, case.get_id, domain)
                case_count += 1 if (indicator_count > 0) else 0
            print "DONE. %d out of %d cases in domain %s had indicators updated." % \
                    (case_count, len(all_cases), domain)
            total_case_count += case_count
        print "CASES ALL DONE. %d cases processed." % total_case_count