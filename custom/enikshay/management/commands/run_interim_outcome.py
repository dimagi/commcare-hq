from __future__ import absolute_import
from __future__ import print_function
import datetime
import csv

from corehq.apps.es import CaseSearchES
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseFactory
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_occurrence_case_from_episode,
    CASE_TYPE_TEST,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    TEST_RESULT_TB_DETECTED,
    TEST_RESULT_TB_NOT_DETECTED,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from six.moves import range


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="The domain to migrate."
        )
        parser.add_argument(
            "log_path",
            help="Path to write the log to"
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually modifies the cases. Without this flag, it's a dry run."
        )

    def handle(self, commit, domain, log_path, **options):
        commit = commit
        factory = CaseFactory(domain)
        headers = [
            'case_id',
            'case_type',
            'test_date_tested',
            'test_result',
            'test_interim_outcome',
            'episode_interim_outcome',
            'episode_interim_outcome_history',
            'datamigration_interim_outcome',
        ]

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        case_ids = [
            hit['_id'] for hit in
            (
                CaseSearchES()
                .domain(domain)
                .case_type("episode")
                .case_property_query("episode_type", "confirmed_drtb", "must")
                .run().hits
            )
        ]

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)
            accessor = CaseAccessors(domain=domain)
            for episode in accessor.iter_cases(case_ids):
                if self.is_valid_case(domain, episode):
                    # Get all follow up tests with a result
                    occurrence = get_occurrence_case_from_episode(domain, episode.case_id)
                    tests = [case for case in accessor.get_reverse_indexed_cases([occurrence.get_id])
                             if case.type == CASE_TYPE_TEST
                             and case.get_case_property('rft_general') == 'follow_up_drtb'
                             and case.get_case_property('result_recorded') == 'yes']
                    tests = sorted(tests, key=lambda test: test.get_case_property('date_tested'))

                    interim_outcome = ''
                    interim_outcome_history = ''
                    for i in range(1, len(tests)):
                        test_interim_outcome = None
                        test_interim_outcome_text = None
                        current_test = tests[i]
                        current_test_date = datetime.datetime.strptime(
                            current_test.get_case_property('date_tested'),
                            "%Y-%m-%d").date()
                        prev_test = tests[i - 1]
                        prev_test_date = datetime.datetime.strptime(
                            prev_test.get_case_property('date_tested'),
                            "%Y-%m-%d").date()
                        if (current_test_date - prev_test_date).days >= 30:
                            if (
                                prev_test.get_case_property('result') == TEST_RESULT_TB_NOT_DETECTED
                                and current_test.get_case_property('result') == TEST_RESULT_TB_NOT_DETECTED
                                and interim_outcome != 'culture_conversion'
                            ):
                                test_interim_outcome = 'culture_conversion'
                                test_interim_outcome_text = "Culture Conversion"
                            elif (
                                prev_test.get_case_property('result') == TEST_RESULT_TB_DETECTED
                                and current_test.get_case_property('result') == TEST_RESULT_TB_DETECTED
                                and interim_outcome == 'culture_conversion'
                            ):
                                test_interim_outcome = 'culture_reversion'
                                test_interim_outcome_text = "Culture Reversion"

                            if test_interim_outcome:
                                interim_outcome = test_interim_outcome
                                interim_outcome_history = prev_test_date.strftime("%d/%m/%y") + ": " + \
                                    test_interim_outcome_text + '\n' + interim_outcome_history

                                writer.writerow([current_test.case_id,
                                                 "test",
                                                 current_test.get_case_property('date_tested'),
                                                 current_test.get_case_property('result'),
                                                 test_interim_outcome,
                                                 None,
                                                 None,
                                                 "yes"])
                                print('Updating {}...'.format(current_test.case_id))
                                case_structure = CaseStructure(
                                    case_id=current_test.case_id,
                                    walk_related=False,
                                    attrs={
                                        "create": False,
                                        "update": {
                                            "interim_outcome": test_interim_outcome,
                                            "datamigration_interim_outcome": "yes",
                                        },
                                    },
                                )
                                if commit:
                                    factory.create_or_update_case(case_structure)
                            else:
                                writer.writerow([current_test.case_id,
                                                 "test",
                                                 current_test.get_case_property('date_tested'),
                                                 current_test.get_case_property('result'),
                                                 None,
                                                 None,
                                                 None,
                                                 "no"])

                    # update episode if needed
                    if interim_outcome:
                        writer.writerow([episode.case_id,
                                         "episode",
                                         None,
                                         None,
                                         None,
                                         interim_outcome,
                                         interim_outcome_history,
                                         "yes"])
                        print('Updating {}...'.format(episode.case_id))
                        case_structure = CaseStructure(
                            case_id=episode.case_id,
                            walk_related=False,
                            attrs={
                                "create": False,
                                "update": {
                                    "interim_outcome": interim_outcome,
                                    "interim_outcome_history": interim_outcome_history,
                                    "datamigration_interim_outcome": "yes",
                                },
                            },
                        )
                        if commit:
                            factory.create_or_update_case(case_structure)
                    else:
                        writer.writerow([episode.case_id,
                                         "episode",
                                         None,
                                         None,
                                         None,
                                         None,
                                         None,
                                         "no"])

        print("Migration finished at {}".format(datetime.datetime.utcnow()))

    def is_valid_case(self, domain, episode):
        if episode.get_case_property('datamigration_interim_outcome') != 'yes':
            # Filter and skip private cases
            try:
                person = get_person_case_from_episode(domain, episode.case_id)
            except ENikshayCaseNotFound:
                return False
            return person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        return False
