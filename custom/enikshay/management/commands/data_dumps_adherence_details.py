from __future__ import absolute_import
from __future__ import print_function

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.users.models import CommCareUser

from custom.enikshay.case_utils import (
    CASE_TYPE_ADHERENCE,
    get_person_case_from_episode,
    get_episode_case_from_adherence,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    1. Adherence Details
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=2059461644
    """
    TASK_NAME = "data_dumps_adherence_details"
    INPUT_FILE_NAME = "data_dumps_adherence_details.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_ADHERENCE

    def get_case_ids_query(self, case_type):
        """
        All open and closed adherence cases 1) whose host/host/host = a person case (open or closed)
        with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (CaseSearchES()
                .domain(DOMAIN)
                .case_type(case_type)
                )

    def include_case_in_dump(self, adherence):
        person = self.get_person(adherence)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        )

    def get_custom_value(self, column_name, adherence):
        if column_name == "Date of Creation of Presumptive TB Episode":
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
        episode = self.get_episode(adherence)
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_episode(self, adherence):
        if 'episode' not in self.context:
            self.context['episode'] = get_episode_case_from_adherence(DOMAIN, adherence.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, adherence, calculation):
        if case_reference == 'person':
            return self.get_person(adherence).get_case_property(calculation)
        elif case_reference == 'episode':
            return self.get_episode(adherence).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)
