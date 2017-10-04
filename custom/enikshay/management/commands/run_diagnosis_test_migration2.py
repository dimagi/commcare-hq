from __future__ import absolute_import, print_function

import csv
import datetime

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_occurrence_case_from_episode, get_person_case_from_episode
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            "log_path",
            help="Path to write the log to"
        )
        parser.add_argument('log_errors')
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
            'current_test_confirming_diagnosis',
            'current_date_of_diagnosis',
            'current_treatment_initiation_date',
            'current_diagnosis_test_result_date',
            'current_diagnosis_lab_facility_name',
            'current_diagnosis_lab_facility_id',
            'current_diagnosis_test_lab_serial_number',
            'current_diagnosis_test_summary',
            'current_diagnosis_test_type',
            'current_diagnosis_test_type_label',
            'info_diagnosis_test_case_id',
            'diagnosis_test_result_date',
            'diagnosis_lab_facility_name',
            'diagnosis_lab_facility_id',
            'diagnosis_test_lab_serial_number',
            'diagnosis_test_summary',
            'diagnosis_test_type',
            'diagnosis_test_type_label',
            'datamigration_diagnosis_test_information2',
        ]

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)

            for episode_case_id in accessor.get_case_ids_in_domain(type='episode'):
                episode = accessor.get_case(episode_case_id)
                case_properties = episode.dynamic_case_properties()

                if self.should_migrate_case(episode_case_id, case_properties, domain):
                    test_confirming_diagnosis = case_properties.get('test_confirmed_diagnosis')
                    date_of_diagnosis = case_properties.get('date_of_diagnosis')
                    treatment_initiation_date = case_properties.get('treatment_initiation_date')
                    current_diagnosis_test_result_date = case_properties.get('diagnosis_test_result_date')
                    current_diagnosis_lab_facility_name = case_properties.get('diagnosis_lab_facility_name')
                    current_diagnosis_lab_facility_id = case_properties.get('diagnosis_lab_facility_id')
                    current_diagnosis_test_lab_serial_number = \
                        case_properties.get('diagnosis_test_lab_serial_number')
                    current_diagnosis_test_summary = case_properties.get('diagnosis_test_summary')
                    current_diagnosis_test_type = case_properties.get('diagnosis_test_type')
                    current_diagnosis_test_type_label = case_properties.get('diagnosis_test_type_label')
                    test_case_id = None
                    diagnosis_test_result_date = None
                    diagnosis_lab_facility_name = None
                    diagnosis_lab_facility_id = None
                    diagnosis_test_lab_serial_number = None
                    diagnosis_test_summary = None
                    diagnosis_test_type = None
                    diagnosis_test_type_label = None
                    datamigration_diagnosis_test_information2 = "no"

                    test = self.get_relevant_test_case(domain, episode)
                    if test is not None and test.get_case_property('test_type_value'):
                        if test.get_case_property('test_type_value') == test_confirming_diagnosis:
                            test_case_id = test.case_id
                            test_case_properties = test.dynamic_case_properties()

                            diagnosis_test_result_date = test_case_properties.get('date_tested', '')
                            diagnosis_lab_facility_name = test_case_properties.get('testing_facility_name', '')
                            diagnosis_lab_facility_id = test_case_properties.get('testing_facility_id', '')
                            diagnosis_test_lab_serial_number = test_case_properties.get('lab_serial_number', '')
                            diagnosis_test_summary = test_case_properties.get('result_summary_display', '')
                            diagnosis_test_type = test_case_properties.get('test_type_value', '')
                            diagnosis_test_type_label = test_case_properties.get('test_type_label', '')
                            datamigration_diagnosis_test_information2 = 'yes',
                        else:
                            # Reset any properties we may have set accidentally in a previous migration
                            diagnosis_test_result_date = ''
                            diagnosis_lab_facility_name = ''
                            diagnosis_lab_facility_id = ''
                            diagnosis_test_lab_serial_number = ''
                            diagnosis_test_summary = ''
                            diagnosis_test_type = test_confirming_diagnosis
                            diagnosis_test_type_label = ''
                            datamigration_diagnosis_test_information2 = "yes"

                        update = {
                            'diagnosis_test_result_date': diagnosis_test_result_date,
                            'diagnosis_lab_facility_name': diagnosis_lab_facility_name,
                            'diagnosis_test_lab_serial_number': diagnosis_test_lab_serial_number,
                            'diagnosis_test_summary': diagnosis_test_summary,
                            'diagnosis_test_type': diagnosis_test_type,
                            'diagnosis_test_type_label': diagnosis_test_type_label,
                            'datamigration_diagnosis_test_information2': datamigration_diagnosis_test_information2,
                        }
                        if commit:
                            factory.update_case(case_id=episode_case_id, update=update)

                    writer.writerow([
                        episode_case_id,
                        test_confirming_diagnosis,
                        date_of_diagnosis,
                        treatment_initiation_date,
                        current_diagnosis_test_result_date,
                        current_diagnosis_lab_facility_name,
                        current_diagnosis_lab_facility_id,
                        current_diagnosis_test_lab_serial_number,
                        current_diagnosis_test_summary,
                        current_diagnosis_test_type,
                        current_diagnosis_test_type_label,
                        test_case_id,
                        diagnosis_test_result_date,
                        diagnosis_lab_facility_name,
                        diagnosis_lab_facility_id,
                        diagnosis_test_lab_serial_number,
                        diagnosis_test_summary,
                        diagnosis_test_type,
                        diagnosis_test_type_label,
                        datamigration_diagnosis_test_information2,
                    ])
        print('Migration complete at {}'.format(datetime.datetime.utcnow()))

    @staticmethod
    def should_migrate_case(case_id, case_properties, domain):
        if (
            case_properties.get('datamigration_diagnosis_test_information2') != 'yes'
            and case_properties.get('episode_type') == 'confirmed_tb'
        ):
            # Filter and skip private cases
            try:
                person = get_person_case_from_episode(domain, case_id)
            except ENikshayCaseNotFound:
                return False
            if person.get_case_property(ENROLLED_IN_PRIVATE) != 'true':
                return True
        return False

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
            and (case.get_case_property('rft_general') == 'diagnosis_dstb'
                 or case.get_case_property('rft_general') == 'diagnosis_drtb')
            and case.get_case_property('result') == 'tb_detected'
        ]

        # Try get a test that matches the episode's test_confirming_diagnosis if set
        test_cases_matching_diagnosis_test_type = [
            case for case in test_cases
            if case.get_case_property('test_type_value') ==
               episode_case.get_case_property('test_confirming_diagnosis')
        ]
        test_cases = test_cases_matching_diagnosis_test_type or test_cases
        
        if test_cases:
            return sorted(test_cases, key=lambda c: c.get_case_property('date_reported'))[-1]
        else:
            return None
