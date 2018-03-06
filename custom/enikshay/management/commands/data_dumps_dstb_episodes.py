from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es import queries

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_person_case_from_episode,
    get_occurrence_case_from_episode,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    DSTB_EPISODE_TYPE,
)
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    1. Episode DSTB cases
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1106002519
    """
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.dump_title = "dstb_episodes"
        self.case_type = CASE_TYPE_EPISODE
        self.input_file_name = os.path.join(os.path.dirname(__file__),
                                            'data_dumps_dstb_episodes.csv')

    def get_case_ids(self, case_type):
        """
        All open and closed episode cases whose host/host = a person case (open
        or closed) with person.dataset = 'real' and person.enrolled_in_private
        != 'true'
        """
        return (CaseSearchES()
                .domain(DOMAIN)
                .case_type(case_type)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true', clause=queries.MUST_NOT)
                .case_property_query("episode_type", DSTB_EPISODE_TYPE, clause=queries.MUST)
                .get_ids())

    def include_case_in_dump(self, episode):
        person = self.get_person(episode)
        return person and person.get_case_property('dataset') == 'real'

    def get_custom_value(self, column_name, episode):
        if column_name == "Current Treating Facility - District":
            if not episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).get_case_property('dto_id')
            else:
                return ''
        elif column_name == "Current Treating Facility - District Name":
            if not episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).get_case_property('dto_name')
            else:
                return ''
        elif column_name == "Current Treating Facility - TU":
            if not episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).get_case_property('tu_id')
            else:
                return ''
        elif column_name == "Current Treating Facility- TU Name":
            if not episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).get_case_property('tu_name')
            else:
                return ''
        elif column_name == "Current Treating Facility - PHI":
            if not episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).owner_id
            else:
                return ''
        elif column_name == "Current Treating Facility - PHI Name":
            if episode.closed and episode.get_case_property('is_active') == 'yes':
                return self.get_person(episode).get_case_property('phi_name')
            else:
                return ''
        return Exception("unknown custom column %s" % column_name)

    def get_person(self, episode):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_occurrence(self, episode):
        if 'occurrence' not in self.context:
            self.context['occurrence'] = get_occurrence_case_from_episode(DOMAIN, episode.case_id)
        return self.context['occurrence']

    def get_case_reference_value(self, case_reference, episode, calculation):
        if case_reference == 'person':
            return self.get_person(episode).get_case_property(calculation)
        elif case_reference == 'occurrence':
            return self.get_occurrence(episode).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)

    def handle(self, *args, **options):
        self.full = options.get('full')
        self.setup()
        self.generate_dump()
