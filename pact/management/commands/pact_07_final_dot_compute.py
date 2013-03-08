from django.core.management.base import NoArgsCommand

from corehq.apps.api.es import FullCaseES

from corehq.apps.users.models import CommCareUser
from pact.api import recompute_dots_casedata
from pact.enums import PACT_DOMAIN
from pact.models import PactPatientCase
from pact.reports.dot import PactDOTPatientField


CHUNK_SIZE = 100


class Command(NoArgsCommand):
    help = "Helper command to compute DOT computed_ fields - to exteranlly operate that operation that should happen on signal firing on submission"
    option_list = NoArgsCommand.option_list + (
    )

    seen_doc_ids = {}

    def handle_noargs(self, **options):
        case_es = FullCaseES(PACT_DOMAIN)
        offset = 0
        dot_cases = PactDOTPatientField.get_pact_cases()

        for case_info in dot_cases:
            case_id = case_info['_id']
            casedoc = PactPatientCase.get(case_id)
            ccuser = CommCareUser.get_by_username('pactimporter@pact.commcarehq.org')
            recompute_dots_casedata(casedoc, ccuser, submit_date=None)

