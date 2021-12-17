from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.covid.management.commands.update_cases import CaseUpdateCommand

BATCH_SIZE = 100
DEVICE_ID = __name__ + ".update_owner_ids"


class Command(CaseUpdateCommand):
    help = "Makes the owner_id for cases blank"

    def case_block(self, case):
        blank_owner_id = {'owner_id': '-'}
        return ElementTree.tostring(CaseBlock.deprecated_init(
            create=False,
            case_id=case.case_id,
            update=blank_owner_id,
        ).as_xml(), encoding='utf-8').decode('utf-8')

    def update_cases(self, domain, case_type, user_id):
        case_ids = self.find_case_ids_by_type(domain, case_type)
        accessor = CaseAccessors(domain)
        case_blocks = []
        errors = []

        print(f"Found {len(case_ids)} {case_type} cases in {domain}")

        for case in accessor.iter_cases(case_ids):
            case_blocks.append(self.case_block(case))

        total_cases_updated = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total_cases_updated += len(chunk)
            print("Updated {} cases on domain {}".format(total_cases_updated, domain))

        print(f"{total_cases_updated} cases of case type {case_type} in domain {domain} had their owner ID"
            " field cleared successfully.")

        self.log_data(domain, "clear_owner_ids", case_type, len(case_ids), total_cases_updated, errors)
