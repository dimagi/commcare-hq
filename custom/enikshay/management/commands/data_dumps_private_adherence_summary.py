from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
import math
from corehq.apps.es import queries
from corehq.apps.locations.models import SQLLocation

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_person_case_from_episode,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.management.commands.base_data_dump import BaseDataDump, PRIVATE_SECTOR_ID_MAPPING
from django.utils.dateparse import parse_date

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    10. Adherence Summary
    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1198090176&range=A43
    """
    TASK_NAME = "11_private_adherence_summary"
    INPUT_FILE_NAME = "data_dumps_private_adherence_summary.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def get_case_ids_query(self, case_type):
        """
        all episode cases
        with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST)
                .case_property_query("episode_type", "confirmed_tb")
                )

    def include_case_in_dump(self, episode):
        try:
            person = self.get_person(episode)
        except ENikshayCaseNotFound as e:
            print("----ENikshayCaseNotFound----")
            print(e)
            print(episode.case_id)
            print("-----------------------------")
            return False
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true' and
            self.person_belongs_to_real_location(person)
        )

    def get_custom_value(self, column_name, episode):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(episode)
            return person_case.case_id
        elif column_name == "Total Doses Expected":
            adherence_latest_date_recorded = episode.get_case_property('adherence_latest_date_recorded')
            if not adherence_latest_date_recorded:
                raise Exception("Adherence latest date recorded not present")
            adherence_schedule_date_start = episode.get_case_property('adherence_schedule_date_start')
            if not adherence_schedule_date_start:
                raise Exception("Adherence schedule date start not present")
            doses_per_week = episode.get_case_property('doses_per_week')
            if not doses_per_week:
                raise Exception("Doses per week not present")
            adherence_latest_date_recorded = parse_date(adherence_latest_date_recorded)
            adherence_schedule_date_start = parse_date(adherence_schedule_date_start)
            if adherence_latest_date_recorded < adherence_schedule_date_start:
                return "adherence not recorded"
            doses_per_week = int(doses_per_week)
            return doses_per_week * (
                math.ceil((adherence_latest_date_recorded - adherence_schedule_date_start).days / 7)
            )
        elif column_name == "No. of missed and unknown doses":
            adherence_latest_date_recorded = episode.get_case_property('adherence_latest_date_recorded')
            if not adherence_latest_date_recorded:
                raise Exception("Adherence latest date recorded not present")
            adherence_schedule_date_start = episode.get_case_property('adherence_schedule_date_start')
            if not adherence_schedule_date_start:
                raise Exception("Adherence schedule date start not present")
            doses_per_week = episode.get_case_property('doses_per_week')
            if not doses_per_week:
                raise Exception("Doses per week not present")
            adherence_total_doses_taken = episode.get_case_property('adherence_total_doses_taken')
            if not adherence_total_doses_taken:
                raise Exception("Adherence total doses taken not present")
            adherence_latest_date_recorded = parse_date(adherence_latest_date_recorded)
            adherence_schedule_date_start = parse_date(adherence_schedule_date_start)
            if adherence_latest_date_recorded < adherence_schedule_date_start:
                return "adherence not recorded"
            doses_per_week = int(doses_per_week)
            adherence_total_doses_taken = int(adherence_total_doses_taken)
            total_expected_doses_taken = doses_per_week * (
                math.ceil((adherence_latest_date_recorded - adherence_schedule_date_start).days / 7)
            )
            return total_expected_doses_taken - int(adherence_total_doses_taken)
        elif column_name == "Total Adherence Score":
            adherence_latest_date_recorded = episode.get_case_property('adherence_latest_date_recorded')
            if not adherence_latest_date_recorded:
                raise Exception("Adherence latest date recorded not present")
            adherence_schedule_date_start = episode.get_case_property('adherence_schedule_date_start')
            if not adherence_schedule_date_start:
                raise Exception("Adherence schedule date start not present")
            doses_per_week = episode.get_case_property('doses_per_week')
            if not doses_per_week:
                raise Exception("Doses per week not present")
            adherence_total_doses_taken = episode.get_case_property('adherence_total_doses_taken')
            if not adherence_total_doses_taken:
                raise Exception("Adherence total doses taken not present")
            adherence_latest_date_recorded = parse_date(adherence_latest_date_recorded)
            adherence_schedule_date_start = parse_date(adherence_schedule_date_start)
            if adherence_latest_date_recorded < adherence_schedule_date_start:
                return "adherence not recorded"
            doses_per_week = int(doses_per_week)
            adherence_total_doses_taken = int(adherence_total_doses_taken)
            total_expected_doses_taken = doses_per_week * (
                math.ceil((adherence_latest_date_recorded - adherence_schedule_date_start).days / 7)
            )
            return (int(adherence_total_doses_taken) / total_expected_doses_taken) * 100
        elif column_name == "Organisation":
            person_case = self.get_person(episode)
            owner_id = person_case.owner_id
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

    def get_person(self, episode):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_case_reference_value(self, case_reference, episode, calculation):
        if case_reference == 'person':
            return self.get_person(episode).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)
