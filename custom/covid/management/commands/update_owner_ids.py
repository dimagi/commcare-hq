from memoized import memoized

from casexml.apps.case.mock import CaseBlock

from corehq.apps.locations.models import SQLLocation
from custom.covid.management.commands.update_cases import CaseUpdateCommand

CHILD_LOCATION_TYPE = 'investigators'


class Command(CaseUpdateCommand):
    help = f"Changes the owner_id of a case to the location_id of the child location with type " \
           f"{CHILD_LOCATION_TYPE} of the current location"

    logger_name = __name__

    @memoized
    def get_location(self, owner_id):
        return SQLLocation.objects.get(location_id=owner_id)

    def case_blocks(self, case):
        owner_id = case.get_case_property('owner_id')
        try:
            location_obj = self.get_location(owner_id)
        except SQLLocation.DoesNotExist:
            self.logger.error("Location does not exist associated with the owner_id:{}. "
                              "Case:{}".format(owner_id, case.case_id))
            return None

        children = location_obj.get_children()
        for child_location in children:
            if child_location.location_type.code == CHILD_LOCATION_TYPE:
                return [CaseBlock(
                    create=False,
                    case_id=case.case_id,
                    owner_id=child_location.location_id,
                )]
