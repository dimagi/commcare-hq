import uuid
from xml.etree import cElementTree as ElementTree

from custom.covid.management.commands.update_cases import CaseUpdateCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


BATCH_SIZE = 100
DEVICE_ID = __name__ + ".add_assignment_cases"


def should_skip(case, location_obj, active_location):
    if location_obj:
        return case.closed or (location_obj.name != active_location)
    else:
        return False


def needs_update(case):
    return case.get_case_property('is_assigned_primary') != 'yes' or \
        case.get_case_property('is_assigned_temp') != 'yes'


def find_owner_id(case, accessor):
    checkin_case = accessor.get_case(case.assigned_to_primary_checkin_case_id)
    return checkin_case.get_case_property('hq_user_id')


class Command(CaseUpdateCommand):
    help = "Creates assignment cases for cases of a specified type in an active location"

    def case_block(self, case, owner_id, assignment_type):
        case_id = uuid.uuid4().hex
        return ElementTree.tostring(CaseBlock.deprecated_init(
            create=True,
            case_id=case_id,
            case_type='assignment',
            owner_id=owner_id,
            index={'parent': (case.get_case_property('case_type'), case.case_id, "extension")},
            update={"assignment_type": assignment_type},
        ).as_xml()).decode('utf-8')

    def update_cases(self, domain, case_type, user_id, active_location):
        case_ids = self.find_case_ids_by_type(domain, case_type)
        accessor = CaseAccessors(domain)

        location_objects = {}
        case_blocks = []
        skip_count = 0
        for case in accessor.iter_cases(case_ids):
            owner_id = case.get_case_property('owner_id')
            if owner_id in location_objects:
                location_obj = location_objects[owner_id]
            else:
                location_obj = SQLLocation.objects.get(location_id=owner_id)
                location_objects[owner_id] = location_obj
            if should_skip(case, location_obj, active_location):
                skip_count += 1
            elif needs_update(case):
                new_owner_id = find_owner_id(case, accessor)
                if case.get_case_property('is_assigned_primary') != 'yes':
                    case_blocks.append(self.case_block(case, new_owner_id, 'primary'))
                elif case.get_case_property('is_assigned_temp') != 'yes':
                    case_blocks.append(self.case_block(case, new_owner_id, 'temp'))
        print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped because they're closed"
              f" or in an inactive location")

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))
