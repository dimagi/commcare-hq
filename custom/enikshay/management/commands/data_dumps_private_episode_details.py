from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from corehq.apps.es import queries
from corehq.apps.locations.models import SQLLocation

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_person_case_from_episode,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    DSTB_EPISODE_TYPE,
)
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    2. Episode details
    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=133934150&range=A41
    """
    TASK_NAME = "02_episode_details"
    INPUT_FILE_NAME = "data_dumps_private_episode_details.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def get_case_ids_query(self, case_type):
        """
        All open and closed episode cases whose host/host = a person case (open
        or closed) with person.dataset = 'real' and person.enrolled_in_private
        != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true')
                .case_property_query("episode_type", DSTB_EPISODE_TYPE)
                )

    def include_case_in_dump(self, episode):
        person = self.get_person(episode)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
        )

    def get_custom_value(self, column_name, episode):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(episode)
            return person_case.case_id
        elif column_name == "Organisation":
            person_case = self.get_person(episode)
            owner_id = person_case.owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                private_sector_org_id = location.metadata.get('private_sector_org_id')
                if private_sector_org_id:
                    return private_sector_org_id
                else:
                    return "Private Sector Organization ID not set for location %s" % private_sector_org_id
            else:
                return "Location not found for id %s" % owner_id
        elif column_name == "Treating Provider Name":
            person_case = self.get_person(episode)
            owner_id = person_case.owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                return location.name
            else:
                return "Location not found with id: %s" % owner_id
        elif column_name == "Treating Hospital Name":
            treating_hospital_id = episode.get_case_property('episode_treating_hospital')
            if treating_hospital_id:
                location = SQLLocation.active_objects.get_or_None(location_id=treating_hospital_id)
                if location:
                    return location.name
                else:
                    return "Treating hospital Location not found with id: %s" % treating_hospital_id
            else:
                return "Treating hospital id not found on case"
        elif column_name == "Associated FO Name":
            episode_fo_id = episode.get_case_property('episode_fo')
            if episode_fo_id:
                location = SQLLocation.active_objects.get_or_None(location_id=episode_fo_id)
                if location:
                    return location.name
                else:
                    return "Episode fo not found with id: %s" % episode_fo_id
            else:
                return "Episode fo id not found on case"
        return Exception("unknown custom column %s" % column_name)

    def get_person(self, episode):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_case_reference_value(self, case_reference, episode, calculation):
        if case_reference == 'person':
            return self.get_person(episode).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)
