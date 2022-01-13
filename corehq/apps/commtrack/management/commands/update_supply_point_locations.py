from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.supply import SupplyPointSQL


def needs_update(case):
    return (case.get('location_id', None) and
            case['owner_id'] != case['location_id'])


def case_block(case):
    return ElementTree.tostring(CaseBlock.deprecated_init(
        create=False,
        case_id=case['_id'],
        owner_id=case['location_id'],
    ).as_xml(), encoding='utf-8')


def get_cases(domain):
    ids = SupplyPointSQL.get_supply_point_ids_by_location(domain).values()
    return SupplyPointSQL.get_supply_points(ids)


def update_supply_points(domain):
    device_id = __name__ + ".update_supply_points"
    case_blocks = (case_block(c) for c in get_cases(domain) if needs_update(c))
    if case_blocks:
        for chunk in chunked(case_blocks, 100):
            submit_case_blocks(chunk, domain, device_id=device_id)
            print("updated {} cases on domain {}".format(len(chunk), domain))


class Command(BaseCommand):
    help = ("Make sure all supply point cases have their owner_id set "
            "to the location_id")

    def handle(self, **options):
        all_domains = Domain.get_all_names()
        total = len(all_domains)
        finished = 0
        for domain in all_domains:
            update_supply_points(domain)
            finished += 1
            if finished % 100 == 0:
                print("Processed {} of {} domains".format(finished, total))
