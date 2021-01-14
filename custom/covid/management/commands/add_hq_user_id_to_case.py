from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import SYSTEM_USER_ID, normalize_username
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


BATCH_SIZE = 100
DEVICE_ID = __name__ + ".add_hq_user_id_to_case"
CASE_TYPE = 'checkin'


def case_block(case, user_id):
    return ElementTree.tostring(CaseBlock.deprecated_init(
        create=False,
        case_id=case.case_id,
        update={'hq_user_id': user_id},
    ).as_xml()).decode('utf-8')


def update_cases(domain, username):
    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain(CASE_TYPE)
    print(f"Found {len(case_ids)} {CASE_TYPE} cases in {domain}")

    user_id = username_to_user_id(username)
    if not user_id:
        user_id = SYSTEM_USER_ID

    case_blocks = []
    skip_count = 0
    for case in accessor.iter_cases(case_ids):
        username_of_associated_mobile_workers = case.get_case_property('username')
        user_id_of_mobile_worker = username_to_user_id(normalize_username(username_of_associated_mobile_workers,
                                                                          domain))
        if user_id_of_mobile_worker:
            case_blocks.append(case_block(case, user_id_of_mobile_worker))
        else:
            skip_count += 1
    print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to unknown username.")

    total = 0
    for chunk in chunked(case_blocks, BATCH_SIZE):
        submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
        total += len(chunk)
        print("Updated {} cases on domain {}".format(total, domain))


class Command(BaseCommand):
    help = "Updates checkin cases to hold the userid of the mobile worker that the checkin case is associated with"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('username')
        parser.add_argument('--and-linked', action='store_true', default=False)

    def handle(self, domain, username, **options):
        domains = {domain}
        if options["and_linked"]:
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        for domain in domains:
            print(f"Processing {domain}")
            update_cases(domain, username)
