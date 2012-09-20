import logging
from django.core.management.base import LabelCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import IndicatorDefinition, CaseIndicatorDefinition
from mvp.models import MVP

class Command(LabelCommand):
    help = ""
    args = ""
    label = ""

    def handle(self, *args, **options):
        case = CommCareCase.get('e92e540066914e6c891954f3eff4a40c')
        all_case_definitions = CaseIndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=MVP.DOMAINS[0])
        for definition in all_case_definitions:
            case.set_definition(definition)
            case.save()
#        for domain in MVP.DOMAINS:
#            key = ["all", domain]
#            all_cases = CommCareCase.view("case/all_cases",
#                reduce=False,
#                include_docs=True,
#                startkey=key,
#                endkey=key+[{}]
#            ).all()
#            all_definitions = IndicatorDefinition.get_all(namespace=MVP.NAMESPACE, domain=domain)
#            for case in all_cases:
#                for definition in all_definitions:
#                    try:
#                        case.set_definition(definition)
#                        case.save()
#                        print "."
#                    except Exception as e:
#                        logging.error("ERROR setting definition %s on case %s: %s" % (definition.slug, case.get_id, e))