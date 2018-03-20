from __future__ import absolute_import
from __future__ import print_function

from corehq.apps.users.models import CommCareUser

from corehq.apps.es import queries

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
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    15. Adherence Details
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=2059461644
    """
    TASK_NAME = "15_adherence_details"
    INPUT_FILE_NAME = "data_dumps_adherence_details.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def get_case_ids_query(self, case_type):
        """
        All open and closed episode cases 1) whose host/host/host = a person case (open or closed)
        with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST_NOT)
                .case_property_filter("episode_type", ["confirmed_tb", "confirmed_drtb"])
                )

    def include_case_in_dump(self, episode):
        assert episode.type == CASE_TYPE_EPISODE
        person = self.get_person(episode)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        )

    def cases_to_dump(self, episode_case):
        assert episode_case.type == CASE_TYPE_EPISODE
        return get_adherence_cases_from_episode(DOMAIN, episode_case.case_id)

    def get_custom_value(self, column_name, adherence):
        assert adherence.type == CASE_TYPE_ADHERENCE, \
            "Unexpected Case type instead of %s" % CASE_TYPE_ADHERENCE
        if column_name == "Date of Creation of Adherence Case":
            return adherence.opened_on
        elif column_name == "Created by Username":
            user_id = None
            try:
                user_id = adherence.opened_by
                return CommCareUser.get_by_user_id(user_id, DOMAIN).username
            except Exception as e:
                return Exception("Could not get username. case opened by %s, %s" % (user_id, e))
        elif column_name == "Created by User ID":
            return adherence.opened_by
        return Exception("unknown custom column %s" % column_name)

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
