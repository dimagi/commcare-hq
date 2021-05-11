from xml.etree import cElementTree as ElementTree

from custom.covid.management.commands.update_cases import CaseUpdateCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

'''This command has an optional argument '--location' that will exclude all cases with that location. If the
case_type is lab_result, the owner_id of that extension case is set to '-'. '''

BATCH_SIZE = 100
DEVICE_ID = __name__ + ".update_case_index_relationship"


def should_skip(case, traveler_location_id, inactive_location):
    if len(case.live_indices) != 1:
        return True
    if case.type == 'contact' and case.get_case_property('has_index_case') == 'no':
        return True
    if traveler_location_id and case.get_case_property('owner_id') == traveler_location_id:
        return True
    if inactive_location and case.get_case_property('owner_id') != inactive_location:
        return True
    return False


def needs_update(case):
    index = case.indices[0]
    if index.referenced_type == "'patient'":
        return True
    return index.relationship == "child" and index.referenced_type == "patient"


def get_owner_id(case_type):
    if case_type == 'lab_result':
        return '-'
    return None


class Command(CaseUpdateCommand):
    help = ("Updates all case indices of a specfied case type to use an extension relationship instead of parent.")

    def case_block(self, case, owner_id):
        index = case.indices[0]
        return ElementTree.tostring(CaseBlock.deprecated_init(
            create=False,
            case_id=case.case_id,
            owner_id=owner_id,
            index={index.identifier: ("patient", index.referenced_id, "extension")},
        ).as_xml(), encoding='utf-8').decode('utf-8')

    def update_cases(self, domain, case_type, user_id):
        inactive_location = self.extra_options['inactive_location']
        accessor = CaseAccessors(domain)
        case_ids = accessor.get_case_ids_in_domain(case_type)
        print(f"Found {len(case_ids)} {case_type} cases in {domain}")
        traveler_location_id = self.extra_options['location']

        case_blocks = []
        skip_count = 0
        for case in accessor.iter_cases(case_ids):
            if should_skip(case, traveler_location_id, inactive_location):
                skip_count += 1
            elif needs_update(case):
                owner_id = get_owner_id(case_type)
                case_blocks.append(self.case_block(case, owner_id))
        print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped due to"
              f" multiple indices.")

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))

        self.log_data(domain, "update_case_index_relationship", case_type, len(case_ids), total, [])

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--location', type=str, default=None)
        parser.add_argument('--inactive-location', type=str, default=None)
