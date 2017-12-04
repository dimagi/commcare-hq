from __future__ import absolute_import, print_function

import csv
import datetime

import six
from django.core.management.base import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import (
    get_all_episode_ids,
    get_all_occurrence_cases_from_person,
    iter_all_active_person_episode_cases,
)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):

        ca = CaseAccessors(domain)
        case_ids = get_all_episode_ids(domain)
        cases = iter_all_active_person_episode_cases(domain, case_ids, sector='private')

        bad_episodes = {}

        for person, _ in with_progress_bar(cases, length=len(case_ids)):
            occurrence_cases = get_all_occurrence_cases_from_person(domain, person.case_id)
            for occurrence_case in occurrence_cases:
                episode_cases = ca.get_reverse_indexed_cases([occurrence_case.case_id])
                open_episode_cases = [case for case in episode_cases
                                      if not case.closed and case.type == 'episode' and
                                      case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
                if len(open_episode_cases) > 1:
                    bad_episodes[occurrence_case] = [c.case_id for c in open_episode_cases]

        print(len(bad_episodes), " bad episodes")

        filename = 'bad_episodes-{}.csv'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['occurrence_id', 'episode_ids'])
            for occurrence_id, bad_cases in six.iteritems(bad_episodes):
                bad_cases.insert(0, occurrence_id)
                writer.writerow(bad_cases)

        print("Output saved in: {}".format(filename))
