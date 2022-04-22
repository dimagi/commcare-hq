from xml.etree import cElementTree as ElementTree

from custom.covid.management.commands.update_cases import CaseUpdateCommand

from casexml.apps.case.mock import CaseBlock

from corehq.form_processor.models import CommCareCase


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
    help = """
        Updates all case indices of a specfied case type to use an extension relationship instead of parent.
        This command has an optional argument '--location' that will exclude all cases with that location. If the
        case_type is lab_result, the owner_id of that extension case is set to '-'.
    """

    logger_name = __name__

    def case_blocks(self, case):
        inactive_location = self.extra_options['inactive_location']
        traveler_location_id = self.extra_options['location']

        if should_skip(case, traveler_location_id, inactive_location):
            return None

        if not needs_update(case):
            return None

        owner_id = get_owner_id(self.case_type)
        index = case.indices[0]
        return [CaseBlock(
            create=False,
            case_id=case.case_id,
            owner_id=owner_id,
            index={index.identifier: ("patient", index.referenced_id, "extension")},
        )]

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--location', type=str, default=None)
        parser.add_argument('--inactive-location', type=str, default=None)
