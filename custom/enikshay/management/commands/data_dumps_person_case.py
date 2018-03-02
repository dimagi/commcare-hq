from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

from corehq.apps.users.models import CommCareUser

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.es import queries

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_PERSON,
    get_all_occurrence_cases_from_person,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump
from custom.enikshay.management.commands.duplicate_occurrences_and_episodes_reconciliation import (
    get_case_recently_modified_on_phone,
)

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """ data dumps for person cases

    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1039030624
    """
    TASK_NAME = "01_person_case"
    INPUT_FILE_NAME = "data_dumps_person_case.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_PERSON

    def get_last_episode(self, case):
        self.context['last_episode'] = (
            self.context.get('last_episode') or
            get_last_episode(case)
        )
        if not self.context['last_episode']:
            return Exception("could not find last episode for person %s" % case.case_id)
        return self.context['last_episode']

    def get_custom_value(self, column_name, case):
        if column_name == "Commcare UUID":
            return case.case_id
        elif column_name == "Created by Username":
            user_id = None
            try:
                user_id = case.opened_by
                user = CommCareUser.get_by_user_id(user_id, DOMAIN)
                return user.username
            except Exception as e:
                return Exception("Could not get username. case opened by %s, %s" % (user_id, e))
        elif column_name == "Created by User ID":
            return case.opened_by
        elif column_name == "Date of creation":
            return case.opened_on
        elif column_name == "Current Owner - PHI":
            return case.owner_id
        elif column_name == 'Person Status':
            if case.closed:
                return "closed"
            elif case.owner_id == "_invalid_":
                return "removed"
            elif case.owner_id == '_archive_':
                return "archived"
            else:
                return "active"
        elif column_name == "Latest Episode creation Date":
            return get_last_episode(case).opened_on
        elif column_name == "Latest Episode Closed?":
            return get_last_episode(case).closed
        elif column_name == "Latest Episode - Date Closed (If any)":
            return get_last_episode(case).closed_on
        raise Exception("unknown custom column %s" % column_name)

    def get_case_reference_value(self, case_reference, case, calculation):
        if case_reference == 'last_episode':
            try:
                return self.get_last_episode(case).get_case_property(calculation)
            except Exception as e:
                return str(e)
        return Exception("unknown case reference %s" % case_reference)

    def get_case_ids_query(self, case_type):
        """
        All open and closed person cases with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST_NOT)
                .case_property_query("dataset", 'real')
                )


def get_all_episode_cases_from_person(domain, person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    return [
        case for case in CaseAccessors(domain).get_reverse_indexed_cases(
            [c.case_id for c in occurrence_cases], case_types=[CASE_TYPE_EPISODE])
    ]


def get_last_episode(person_case):
    """
    For all episode cases under the person (the host of the host of the episode is the primary person case):
        If count(open episode cases with episode.is_active = 'yes') > 1, report error
        If count(open episode cases with episode.is_active = 'yes') = 1, pick this case
        If count(open episode cases with episode.is_active = 'yes') = 0:
            pick the episode with the latest episode.closed_date if there is one
            Else report 'No episodes'
    """
    episode_cases = get_all_episode_cases_from_person(person_case.domain, person_case.case_id)
    open_episode_cases = [
        episode_case for episode_case in episode_cases
        if not episode_case.closed
    ]
    active_open_episode_cases = [
        episode_case for episode_case in open_episode_cases
        if episode_case.get_case_property('is_active') == 'yes'
    ]
    if len(active_open_episode_cases) > 1:
        raise Exception("Multiple active open episode cases found for %s" % person_case.case_id)
    elif len(active_open_episode_cases) == 1:
        return active_open_episode_cases[0]
    else:
        # look for case recently modified by a user
        recently_modified_case_on_phone = get_case_recently_modified_on_phone(episode_cases, False)
        if recently_modified_case_on_phone:
            return recently_modified_case_on_phone

        # else look for the case recently modified ever
        # for ex cases that were created and then closed by the system itself
        recently_modified_case = get_case_recently_modified(episode_cases)
        if recently_modified_case:
            return recently_modified_case

        raise Exception("No episodes for %s" % person_case.case_id)


def get_case_recently_modified(all_cases):
    recently_modified_case = None
    recently_modified_time = None
    for case in all_cases:
        last_edit = case.modified_on
        if last_edit:
            if recently_modified_time is None:
                recently_modified_time = last_edit
                recently_modified_case = case
            elif recently_modified_time and recently_modified_time < last_edit:
                recently_modified_time = last_edit
                recently_modified_case = case
            elif recently_modified_time and recently_modified_time == last_edit:
                print("This looks like a super edge case that can be looked at. "
                      "Not blocking as of now. Case id: {case_id}".format(case_id=case.case_id))

    return recently_modified_case
