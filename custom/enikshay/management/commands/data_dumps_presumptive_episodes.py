from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from corehq.apps.es import case_search
from corehq.apps.users.models import CommCareUser

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_person_case_from_episode,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    2. Presumptive TB cases
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1177413224
    """
    TASK_NAME = "02_presumptive_episodes"
    INPUT_FILE_NAME = "data_dumps_presumptive_episodes.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE

    def get_case_ids_query(self, case_type):
        """
        All open and closed episode cases whose host/host = a person case (open
        or closed) with person.dataset = 'real' and self.enrolled_in_private !=
        'true' and self.episode_type = 'presumptive_tb'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .NOT(case_search.case_property_filter(ENROLLED_IN_PRIVATE, 'true'))
                .case_property_filter('episode_type', 'presumptive_tb')
                )

    def include_case_in_dump(self, episode):
        person = self.get_person(episode)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        )

    def get_custom_value(self, column_name, episode):
        if column_name == "Commcare UUID":
            return episode.case_id
        elif column_name == "Episode closed?":
            return episode.closed
        elif column_name == "Date of Creation of Presumptive TB Episode":
            return episode.opened_on
        elif column_name == 'Created by Username':
            user_id = None
            try:
                user_id = episode.opened_by
                user = CommCareUser.get_by_user_id(user_id, DOMAIN)
                return user.username
            except Exception as e:
                return Exception("Could not get username. case opened by %s, %s" % (user_id, e))
        elif column_name == "Created by User ID":
            return episode.opened_by
        raise Exception("No custom calculation found for {}".format(column_name))

    def get_person(self, episode):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_case_reference_value(self, case_reference, episode, calculation):
        if case_reference == 'person':
            return self.get_person(episode).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)
