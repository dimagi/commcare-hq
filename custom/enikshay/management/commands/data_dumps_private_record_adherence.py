from __future__ import absolute_import
from __future__ import print_function

from corehq.apps.es import queries
from corehq.apps.locations.models import SQLLocation

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_ADHERENCE,
    get_person_case_from_episode,
    get_episode_case_from_adherence,
    get_adherence_cases_from_episode,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.management.commands.base_data_dump import BaseDataDump, PRIVATE_SECTOR_ID_MAPPING

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    09. Record Adherence
    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1444087620&range=A42
    """
    TASK_NAME = "09_record_adherence"
    INPUT_FILE_NAME = "data_dumps_private_record_adherence.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def get_case_ids_query(self, case_type):
        """
        all adherence cases
        with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST)
                )

    def include_case_in_dump(self, episode):
        assert episode.type == CASE_TYPE_EPISODE
        try:
            person = self.get_person(episode)
        except ENikshayCaseNotFound:
            return False
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true' and
            self.person_belongs_to_real_location(person)
        )

    def cases_to_dump(self, episode_case):
        assert episode_case.type == CASE_TYPE_EPISODE
        return get_adherence_cases_from_episode(DOMAIN, episode_case.case_id)

    def get_custom_value(self, column_name, adherence):
        assert adherence.type == CASE_TYPE_ADHERENCE, \
            "Unexpected Case type instead of %s" % CASE_TYPE_ADHERENCE
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(adherence)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            episode_case = self.get_episode(adherence)
            return episode_case.case_id
        elif column_name == "Organisation":
            owner_id = self.get_person(adherence).owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                private_sector_org_id = location.metadata.get('private_sector_org_id')
                if private_sector_org_id:
                    return PRIVATE_SECTOR_ID_MAPPING.get(private_sector_org_id, private_sector_org_id)
                else:
                    raise Exception("Private Sector Organization ID not set for location %s" % owner_id)
            else:
                raise Exception("Location not found for id %s" % owner_id)
        raise Exception("unknown custom column %s" % column_name)

    def get_person(self, adherence):
        assert adherence.type in [CASE_TYPE_ADHERENCE, CASE_TYPE_EPISODE], \
            "Unexpected Case type instead of %s and %s" % (CASE_TYPE_ADHERENCE, CASE_TYPE_EPISODE)

        if 'person' not in self.context:
            if adherence.type == CASE_TYPE_EPISODE:
                episode = adherence
            else:
                episode = self.get_episode(adherence)
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_episode(self, adherence):
        assert adherence.type == CASE_TYPE_ADHERENCE
        if 'episode' not in self.context:
            self.context['episode'] = get_episode_case_from_adherence(DOMAIN, adherence.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, adherence, calculation):
        if case_reference == 'person':
            return self.get_person(adherence).get_case_property(calculation)
        elif case_reference == 'episode':
            return self.get_episode(adherence).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)
