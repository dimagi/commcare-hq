from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import normalize_username
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.covid.management.commands.update_cases import CaseUpdateCommand

BATCH_SIZE = 100
DEVICE_ID = __name__ + ".add_hq_user_id_to_case"
CASE_TYPE = 'checkin'


class Command(CaseUpdateCommand):
    help = "Updates checkin cases to hold the userid of the mobile worker that the checkin case is associated with"

    def case_block(self, case, user_id):
        return ElementTree.tostring(CaseBlock.deprecated_init(
            create=False,
            case_id=case.case_id,
            update={'hq_user_id': user_id},
        ).as_xml()).decode('utf-8')

    def update_cases(self, domain, user_id):
        case_ids = self.find_case_ids_by_type(domain, CASE_TYPE)
        accessor = CaseAccessors(domain)
        case_blocks = []
        skip_count = 0
        for case in accessor.iter_cases(case_ids):
            username_of_associated_mobile_workers = case.get_case_property('username')
            user_id_of_mobile_worker = username_to_user_id(normalize_username(username_of_associated_mobile_workers,
                                                                              domain))
            if user_id_of_mobile_worker:
                case_blocks.append(self.case_block(case, user_id_of_mobile_worker))
            else:
                skip_count += 1
        print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to unknown username.")

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))
