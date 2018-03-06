from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
from corehq.apps.es import case_search

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    get_person_case_from_episode,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    1. Presumptive TB cases
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1177413224
    """
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_EPISODE
        self.input_file_name = os.path.join(os.path.dirname(__file__),
                                            'data_dumps_presumptive_episodes.csv')

    def get_case_ids(self, case_type):
        """
        All open and closed episode cases whose host/host = a person case (open
        or closed) with person.dataset = 'real' and self.enrolled_in_private !=
        'true' and self.episode_type = 'presumptive_tb'
        """
        return (case_search.CaseSearchES()
                .domain(DOMAIN)
                .case_type(case_type)
                .NOT(case_search.case_property_filter(ENROLLED_IN_PRIVATE, 'true'))
                .case_property_filter('episode_type', 'presumptive_tb')
                .size(10)  # FIXME size limited for debugging
                .get_ids())

    def include_case_in_dump(self, episode):
        person = self.get_person(episode)
        return person and person.get_case_property('dataset') == 'real'

    def get_custom_value(self, column_name, episode):
        if column_name == 'Created by Username':
            return (episode.get_case_property('opened_by_username')
                    or episode.get_case_property('opened_by_username1'))
        raise Exception("No custom calculation found for {}".format(column_name))

    def get_person(self, episode):
        if 'person' not in self.context:
            self.context['person'] = get_person_case_from_episode(DOMAIN, episode.case_id)
        return self.context['person']

    def get_case_reference_value(self, case_reference, episode, calculation):
        if case_reference == 'person':
            return self.get_person(episode).get_case_property(calculation)
        return Exception("unknown case reference %s" % case_reference)

    def handle(self, *args, **options):
        self.setup()
        self.generate_dump()
