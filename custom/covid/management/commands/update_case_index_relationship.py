from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


BATCH_SIZE = 100
CASE_TYPE = "lab_result"
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


def update_cases(domain):
    accessor = CaseAccessors(domain)
    case_ids = accessor.get_case_ids_in_domain(CASE_TYPE)
    print(f"Found {len(case_ids)} {CASE_TYPE} cases in {domain}")

    case_blocks = []
    skip_count = 0
    for case_id in case_ids:
        case = accessor.get_case(case_id)
        if should_skip(case):
            skip_count += 1
        elif needs_update(case):
            case_blocks.append(case_block(case))
    print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to multiple indices.")

    total = 0
    for chunk in chunked(case_blocks, BATCH_SIZE):
        submit_case_blocks(chunk, domain, device_id=DEVICE_ID)
        total += len(chunk)
        print("Updated {} cases on domain {}".format(total, domain))


class Command(BaseCommand):
    help = (f"Updates all {CASE_TYPE} case indices to use an extension relationship instead of parent.")

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--and-linked', action='store_true', default=False)

    def handle(self, domain, **options):
        domains = {domain}
        if options["and_linked"]:
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        for domain in domains:
            print(f"Processing {domain}")
            update_cases(domain)
