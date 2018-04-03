from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree
from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import submit_case_blocks


def needs_update(case):
    return (case.get('location_id', None) and
            case['owner_id'] != case['location_id'])


def case_block(case):
    return ElementTree.tostring(CaseBlock(
        create=False,
        case_id=case['_id'],
        owner_id=case['location_id'],
    ).as_xml())


def get_cases(domain):
    supply_point_ids = (case['id'] for case in CommCareCase.get_db().view(
        'supply_point_by_loc/view',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=False,
        include_docs=False,
    ).all())
    return iter_docs(CommCareCase.get_db(), supply_point_ids)


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
