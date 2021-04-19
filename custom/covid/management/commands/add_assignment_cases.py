import uuid
from xml.etree import cElementTree as ElementTree

from corehq.form_processor.exceptions import CaseNotFound
from custom.covid.management.commands.update_cases import CaseUpdateCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


BATCH_SIZE = 100
DEVICE_ID = __name__ + ".add_assignment_cases"


def needs_update(case):
    return case.get_case_property('is_assigned_primary') == 'yes' or \
        case.get_case_property('is_assigned_temp') == 'yes'


def find_owner_id(case, accessor, case_property):
    try:
        checkin_case = accessor.get_case(case.get_case_property(case_property))
        return checkin_case.get_case_property('hq_user_id')
    except CaseNotFound:
        print("CaseNotFound: case:{} no matching case for this case's {}".format(case.case_id, case_property))
        return None


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

    def update_cases(self, domain, case_type, user_id):
        accessor = CaseAccessors(domain)
        location_id = self.extra_options['location']
        if location_id is None:
            case_ids = []
            print("Warning: no active location was entered")
        else:
            case_ids = accessor.get_open_case_ids_in_domain_by_type(case_type, owner_ids=[location_id])

        case_blocks = []
        errors = []
        skip_count = 0
        for case in accessor.iter_cases(case_ids):
            if case.get_case_property('current_status') == 'closed':
                skip_count += 1
            elif needs_update(case):
                new_primary_owner_id = find_owner_id(case, accessor, 'assigned_to_primary_checkin_case_id')
                new_temp_owner_id = find_owner_id(case, accessor, 'assigned_to_temp_checkin_case_id')
                case_created = False
                if case.get_case_property('is_assigned_primary') == 'yes' and new_primary_owner_id:
                    case_blocks.append(self.case_block(case, new_primary_owner_id, 'primary'))
                    case_created = True
                if case.get_case_property('is_assigned_temp') == 'yes' and new_temp_owner_id:
                    case_blocks.append(self.case_block(case, new_temp_owner_id, 'temp'))
                    case_created = True
                if not case_created:
                    invalid_primary_id = case.get_case_property('assigned_to_primary_checkin_case_id')
                    invalid_temp_id = case.get_case_property('assigned_to_temp_checkin_case_id')
                    errors.append("CaseNotFound: case:{} no matching case for this case's "
                                  "assigned_to_primary_checkin_case_id:{} or assigned_to_temp_checkin_case_id:"
                                  "{}".format(case.case_id, invalid_primary_id, invalid_temp_id))
                    skip_count += 1
        print(f"{len(case_blocks)} to update in {domain}, {skip_count} cases have skipped because they're closed"
              f" or in an inactive location")

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))

        self.log_data(domain, "add_assignment_cases", case_type, len(case_ids), total, errors, loc_id=location_id)

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--location', type=str, default=None)
