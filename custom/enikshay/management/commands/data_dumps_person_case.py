from __future__ import absolute_import
from __future__ import print_function
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es import queries

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_all_occurrence_cases_from_person,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    data dumps for person cases
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1039030624
    """

    def get_last_episode(self, case):
        self.context['last_episode'] = (
            self.context['last_episode'] or
            get_last_episode(case)
        )
        return self.context['last_episode']

    def get_custom_value(self, column_name, case):
        if column_name == 'Reason for "Remove a Person" / Closure':
            if case.closed:
                return "closed"
            elif case.owner_id == "_invalid_":
                return "removed"
            elif case.owner_id == '_archive_':
                return "archived"
            else:
                return "active"
        elif column_name == 'Latest Episode - Date Closed (If any)':
            try:
                last_episode_case = self.get_last_episode(case)
                if last_episode_case.closed:
                    return "closed"
                else:
                    return "open"
            except Exception as e:
                return str(e)

    def get_case_reference_value(self, case_reference, case, calculation):
        if case_reference == 'last_episode':
            try:
                return self.get_last_episode(case).get_case_property(calculation)
            except Exception as e:
                return str(e)
        return Exception("unknown case reference %s" % case_reference)

    def handle(self, case_type, input_file_name, *args, **options):
        self.case_type = case_type
        self.input_file_name = input_file_name
        self.setup()
        self.generate_dump()

    def get_case_ids(self, case_type):
        """
        All open and closed person cases with person.dataset = 'real' and person.enrolled_in_private != 'true'
        """
        return (CaseSearchES()
                .domain(DOMAIN)
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST_NOT)
                .case_property_query("dataset", 'real')
                .get_ids()[0:10])


def get_recently_closed_case(all_cases):
    recently_closed_case = None
    recently_closed_time = None
    for case in all_cases:
        case_closed_time = case.closed_on
        if case_closed_time:
            if recently_closed_time is None:
                recently_closed_time = case_closed_time
                recently_closed_case = case
            elif recently_closed_time and recently_closed_time < case_closed_time:
                recently_closed_time = case_closed_time
                recently_closed_case = case
            elif recently_closed_time and recently_closed_time == case_closed_time:
                raise Exception("This looks like a super edge case that can be looked at. "
                                "Not blocking as of now. Case id: {case_id}".format(case_id=case.case_id))

    return recently_closed_case


def get_all_episode_cases_from_person(domain, person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(domain, person_case_id)
    return [
        case for case in CaseAccessors(domain).get_reverse_indexed_cases(
            [c.case_id for c in occurrence_cases], case_types=[CASE_TYPE_EPISODE])
    ]


def get_last_episode(person_case):
    """
    For all episode cases under the person (the host of the host of the episode is the primary person case)
    If count(open episode cases with episode.is_active = 'yes') > 1, report error
    If count(open episode cases with episode.is_active = 'yes') = 1, pick this case
    If count(open episode cases with episode.is_active = 'yes') = 0:
        If count(open episode cases) > 0, report error
    Else, pick the episode with the latest episode.closed_date
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
    elif len(open_episode_cases) > 0:
        raise Exception("Open inactive episode cases found for %s" % person_case.case_id)
    else:
        return get_recently_closed_case(episode_cases)
