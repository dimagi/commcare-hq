import datetime

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock

from corehq.apps.es import CaseSearchES
from corehq.apps.hqcase.bulk import update_cases
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id

DEVICE_ID = __name__


class Command(BaseCommand):
    help = ("One-off script created 2022-02-03. A bunch of cases had the "
            "property all_activity_complete_date inadvertently set to the string "
            "'date(today())' rather than '2022-02-02'.  This corrects that.")

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--username', type=str, default=None)
        parser.add_argument('--and-linked', action='store_true', default=False)
        parser.add_argument('--output-file', type=str, default=None)

    def handle(self, domain, **options):
        domains = {domain}
        if options["and_linked"]:
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}
            print(f"Running against {len(domains)} total domains")

        if options["username"]:
            user_id = username_to_user_id(options["username"])
            if not user_id:
                raise Exception("The username you entered is invalid")
        else:
            user_id = SYSTEM_USER_ID

        for domain in sorted(domains):
            bad_case_ids = _get_bad_case_ids(domain)
            print(f"Updating {len(bad_case_ids)} cases on {domain}")
            update_cases(domain, _correct_bad_property, bad_case_ids, user_id, DEVICE_ID)


def _get_bad_case_ids(domain):
    return list(CaseSearchES()
                .domain(domain)
                .case_property_query("all_activity_complete_date", "date(today())")
                .modified_range(gte=datetime.date(2022, 2, 2))
                .case_type(["patient", "contact"])
                .scroll_ids())


def _correct_bad_property(case):
    if case.get_case_property('all_activity_complete_date') == 'date(today())':
        return CaseBlock(
            create=False,
            case_id=case.case_id,
            update={"all_activity_complete_date": "2022-02-02"},
        )
