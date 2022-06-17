import uuid
from xml.etree import cElementTree as ElementTree

from corehq.form_processor.exceptions import CaseNotFound
from custom.covid.management.commands.update_cases import CaseUpdateCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.models import CommCareCase


BATCH_SIZE = 100
DEVICE_ID = __name__ + ".add_assignment_cases"


def needs_update(case):
    return case.get_case_property('is_assigned_primary') == 'yes' or \
        case.get_case_property('is_assigned_temp') == 'yes'


def find_owner_id(case, case_property):
    try:
        case_id = case.get_case_property(case_property)
        checkin_case = CommCareCase.objects.get_case(case_id, case.domain)
        return checkin_case.get_case_property('hq_user_id')
    except CaseNotFound:
        print("CaseNotFound: case:{} no matching case for this case's {}".format(case.case_id, case_property))
        return None


class Command(CaseUpdateCommand):
    help = "Creates assignment cases for cases of a specified type in an active location"

    logger_name = __name__

    def _case_block(self, case, owner_id, assignment_type):
        case_id = uuid.uuid4().hex
        return CaseBlock(
            create=True,
            case_id=case_id,
            case_type='assignment',
            owner_id=owner_id,
            index={'parent': (case.get_case_property('case_type'), case.case_id, "extension")},
            update={"assignment_type": assignment_type},
        )

    def find_case_ids(self, domain):
        location_id = self.extra_options['location']
        if location_id is None:
            print("Warning: no active location was entered")
            return []
        return CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain, self.case_type, owner_ids=[location_id])

    def case_blocks(self, case):
        if case.get_case_property('current_status') == 'closed':
            return None

        if not needs_update(case):
            return None

        case_blocks = []
        new_primary_owner_id = find_owner_id(case, 'assigned_to_primary_checkin_case_id')
        new_temp_owner_id = find_owner_id(case, 'assigned_to_temp_checkin_case_id')
        case_created = False
        if case.get_case_property('is_assigned_primary') == 'yes' and new_primary_owner_id:
            case_blocks.append(self._case_block(case, new_primary_owner_id, 'primary'))
            case_created = True
        if case.get_case_property('is_assigned_temp') == 'yes' and new_temp_owner_id:
            case_blocks.append(self._case_block(case, new_temp_owner_id, 'temp'))
            case_created = True
        if not case_created:
            invalid_primary_id = case.get_case_property('assigned_to_primary_checkin_case_id')
            invalid_temp_id = case.get_case_property('assigned_to_temp_checkin_case_id')
            self.logger.error("CaseNotFound: case:{} no matching case for this case's "
                              "assigned_to_primary_checkin_case_id:{} or assigned_to_temp_checkin_case_id:"
                              "{}".format(case.case_id, invalid_primary_id, invalid_temp_id))
        return case_blocks

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--location', type=str, default=None)
