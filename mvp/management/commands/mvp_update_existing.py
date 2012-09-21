import logging
from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormIndicatorDefinition, DocumentMistmatchError
from couchforms.models import XFormInstance
from mvp.models import MVP, MVPCannotFetchCaseError

class Command(LabelCommand):
    help = "Update MVP indicators in existing cases and forms."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_child_visit_forms = XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A"
        ).all()
        all_household_visit_forms = XFormInstance.view("couchforms/by_xmlns",
            reduce=False,
            include_docs=True,
            key="http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B"
        ).all()
        all_forms = all_child_visit_forms + all_household_visit_forms

        for domain in MVP.DOMAINS:
            all_form_definitions = FormIndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=domain)
            for form in all_forms:
                for definition in all_form_definitions:
                    try:
                        form.set_definition(definition)
                        form.save()
                    except ResourceNotFound:
                        print "ResourceNotFound triggered by form:", form.get_id
                    except DocumentMistmatchError:
                        pass
                    except MVPCannotFetchCaseError:
                        pass

        for domain in MVP.DOMAINS:
            key = ["all", domain]
            all_cases = CommCareCase.view("case/all_cases",
                reduce=False,
                include_docs=True,
                startkey=key,
                endkey=key+[{}]
            ).all()
            all_case_definitions = CaseIndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=domain)
            for case in all_cases:
                for definition in all_case_definitions:
                    try:
                        case.set_definition(definition)
                        case.save()
                    except Exception:
                        pass