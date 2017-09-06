from __future__ import absolute_import, print_function

import datetime

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_occurrence_case_from_episode
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            "log_path",
            help="Path to write the log to"
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="Actually modifies the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, log_path, **options):
        commit = options['commit']
        accessor = CaseAccessors(domain)
        factory = CaseFactory(domain)
        headers = [
            'case_id',
            'diagnosis_test_result_date',
            'diagnosis_lab_facility_name',
            'diagnosis_test_lab_serial_number',
            'diagnosis_test_summary',
            'datamigration_diagnosis_test_information',
        ]
        row_format = ','.join(['{' + header + '}' for header in headers[1:]])

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        with open(log_path, "w") as log_file:
            print(','.join(headers), file=log_file)

            for episode_case_id in accessor.get_case_ids_in_domain(type='episode'):
                print('Looking at {}'.format(episode_case_id))
                episode_case = accessor.get_case(episode_case_id)
                case_properties = episode_case.dynamic_case_properties()

                if self.should_migrate_case(case_properties):
                    test = self.get_relevant_test_case(domain, episode_case)

                    if test is not None:
                        update = self.get_updates(test)
                        print('Updating {}...'.format(episode_case_id))
                        print(episode_case_id + ',' + row_format.format(**update), file=log_file)

                        if commit:
                            factory.update_case(case_id=episode_case_id, update=update)
                    else:
                        print('No relevant test found for episode {}'.format(episode_case_id))
                else:
                    print('Do not migrate {}'.format(episode_case_id))

        print('Migration complete at {}'.format(datetime.datetime.utcnow()))

    @staticmethod
    def should_migrate_case(case_properties):
        return (
            case_properties.get('datamigration_diagnosis_test_information') != 'yes'
            and case_properties.get('episode_type') == 'confirmed_tb'
            and case_properties.get('treatment_initiated') == 'yes_phi'
            and case_properties.get('diagnosis_test_result_date', '') == ''
        )

    @staticmethod
    def get_relevant_test_case(domain, episode_case):
        try:
            occurrence_case = get_occurrence_case_from_episode(domain, episode_case.case_id)
        except ENikshayCaseNotFound:
            return None

        indexed_cases = CaseAccessors(domain).get_reverse_indexed_cases([occurrence_case.case_id])
        test_cases = [
            case for case in indexed_cases
            if case.type == 'test'
            and case.get_case_property('rft_general') == 'diagnosis_dstb'
            and case.get_case_property('result') == 'tb_detected'
        ]
        if test_cases:
            return sorted(test_cases, key=lambda c: c.get_case_property('date_reported'))[-1]
        else:
            return None

    @staticmethod
    def get_updates(test):
        test_case_properties = test.dynamic_case_properties()
        return {
            'diagnosis_test_result_date': test_case_properties.get('date_tested', ''),
            'diagnosis_lab_facility_name': test_case_properties.get('testing_facility_name', ''),
            'diagnosis_test_lab_serial_number': test_case_properties.get('lab_serial_number', ''),
            'diagnosis_test_summary': test_case_properties.get('result_summary_display', ''),
            'datamigration_diagnosis_test_information': 'yes',
        }
