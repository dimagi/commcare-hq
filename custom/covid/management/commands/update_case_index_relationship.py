from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


BATCH_SIZE = 100
DEVICE_ID = __name__ + ".update_case_index_relationship"


def should_skip(case):
    return len(case.indices) != 1


def needs_update(case):
    index = case.indices[0]
    return index.referenced_type == "patient" and index.relationship == "child"


def case_block(case):
    index = case.indices[0]
    return ElementTree.tostring(CaseBlock.deprecated_init(
        create=False,
        case_id=case.case_id,
        owner_id='-',
        index={index.identifier: (index.referenced_type, index.referenced_id, "extension")},
    ).as_xml()).decode('utf-8')


def update_cases(domain, case_type, username):
    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain(case_type)
    print(f"Found {len(case_ids)} {case_type} cases in {domain}")

    user_id = username_to_user_id(username)

    case_blocks = []
    skip_count = 0
    for case in accessor.iter_cases(case_ids):
        if should_skip(case):
            skip_count += 1
        elif needs_update(case):
            case_blocks.append(case_block(case))
    print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to multiple indices.")

    total = 0
    for chunk in chunked(case_blocks, BATCH_SIZE):
        submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
        total += len(chunk)
        print("Updated {} cases on domain {}".format(total, domain))


class Command(BaseCommand):
    help = ("Updates all case indices of a specfied case type to use an extension relationship instead of parent.")

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('username')
        parser.add_argument('--and-linked', action='store_true', default=False)

    def handle(self, domain, case_type, username, **options):
        domains = {domain}
        if options["and_linked"]:
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        for domain in domains:
            print(f"Processing {domain}")
            update_cases(domain, case_type, username)
