from casexml.apps.case.mock import CaseBlock

from corehq.apps.locations.models import SQLLocation
from custom.covid.management.commands.update_cases import CaseUpdateCommand

CHILD_LOCATION_TYPE = 'investigators'


class Command(CaseUpdateCommand):
    help = f"Changes the owner_id of a case to the location_id of the child location with type " \
           f"{CHILD_LOCATION_TYPE} of the current location"

    locations_objects = None

    def logger_name(self):
        return __name__

    def get_location(self, owner_id):
        if self.locations_objects is None:
            self.locations_objects = {}

        if owner_id in self.locations_objects:
            return self.locations_objects[owner_id]

        loc = SQLLocation.objects.get(location_id=owner_id)
        self.locations_objects[owner_id] = loc
        return loc

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
