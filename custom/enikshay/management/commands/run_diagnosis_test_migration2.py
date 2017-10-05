from __future__ import absolute_import, print_function

import csv
from datetime import datetime

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import get_occurrence_case_from_episode, get_person_case_from_episode
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import ENikshayCaseNotFound

TEST_TO_LABEL = {
    'microscopy-zn': "Microscopy-ZN",
    'microscopy-fluorescent': "Microscopy-Fluorescent",
    'other_dst_tests': "Other DST Tests",
    'other_clinical_tests': "Other Clinical Tests",
    'tst': "TST",
    'igra': "IGRA",
    'chest_x-ray': "Chest X-ray",
    'cytopathology': "Cytopathology",
    'histopathology': "Histopathology",
    'cbnaat': "CBNAAT",
    'culture': "Culture",
    'dst': "DST",
    'line_probe_assay': "Line Probe Assay",
    'fl_line_probe_assay': "FL LPA",
    'sl_line_probe_assay': "SL LPA",
    'gene_sequencing': "Gene Sequencing",
    'other_clinical': "Other Clinical",
    'other_dst': "Other DST",
}


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
            'datamigration_diagnosis_test_information',
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
            'flag_for_review',
            'datamigration_diagnosis_test_information2',
        ]

        print("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.utcnow()
        ))

        with open(log_path, "w") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(headers)

            for episode_case_id in with_progress_bar(accessor.get_case_ids_in_domain(type='episode')):
                episode = accessor.get_case(episode_case_id)
                case_properties = episode.dynamic_case_properties()

                if self.should_migrate_case(episode_case_id, case_properties, domain):
                    test_confirming_diagnosis = case_properties.get('test_confirming_diagnosis')
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
                    datamigration_diagnosis_test_information = \
                        case_properties.get('datamigration_diagnosis_test_information')
                    test_case_id = None
                    diagnosis_test_result_date = ''
                    diagnosis_lab_facility_name = ''
                    diagnosis_lab_facility_id = ''
                    diagnosis_test_lab_serial_number = ''
                    diagnosis_test_summary = ''
                    diagnosis_test_type = ''
                    diagnosis_test_type_label = ''
                    flag_for_review = ''
                    datamigration_diagnosis_test_information2 = "no"

                    date_format = "%Y-%m-%d"
                    comparison_date = date_of_diagnosis or treatment_initiation_date
                    test_type = test_confirming_diagnosis or current_diagnosis_test_type
                    if comparison_date and test_type:
                        test = self.get_relevant_test_case(domain, episode, test_type)
                        # logic to make sure test we found is close to date of diagnosis
                        if (
                            test and test.get_case_property("date_tested")
                            and abs((
                                datetime.strptime(comparison_date, date_format) -
                                datetime.strptime(test.get_case_property("date_tested"), date_format)
                            ).days) <= 30
                        ):
                            test_case_id = test.case_id
                            test_case_properties = test.dynamic_case_properties()
                            diagnosis_test_result_date = test_case_properties.get('date_tested', '')
                            diagnosis_lab_facility_name = test_case_properties.get('testing_facility_name', '')
                            diagnosis_lab_facility_id = test_case_properties.get('testing_facility_id', '')
                            diagnosis_test_lab_serial_number = test_case_properties.get('lab_serial_number', '')
                            diagnosis_test_summary = test_case_properties.get('result_summary_display', '')
                            diagnosis_test_type = test_case_properties.get('test_type_value', '')
                            diagnosis_test_type_label = test_case_properties.get('test_type_label', '')
                            datamigration_diagnosis_test_information2 = 'yes'
                        else:
                            if test_confirming_diagnosis:
                                # Reset any properties we may have set accidentally in a previous migration
                                diagnosis_test_type = test_confirming_diagnosis
                                diagnosis_test_type_label = TEST_TO_LABEL.get(test_confirming_diagnosis,
                                                                              test_confirming_diagnosis)
                                datamigration_diagnosis_test_information2 = "yes"
                            elif datamigration_diagnosis_test_information == "yes":
                                # The previous migration messed up this case.
                                # Find the form that first set diagnosis_test_type and
                                # reset all diagnosis properties from there
                                flag_for_review = "yes"
                                diagnosis_update = self._get_diagnosis_update(episode).\
                                    get_update_action().dynamic_properties
                                diagnosis_test_result_date = diagnosis_update.\
                                    get('diagnosis_test_result_date', '')
                                diagnosis_lab_facility_name = diagnosis_update.\
                                    get('diagnosis_lab_facility_name', '')
                                diagnosis_lab_facility_id = diagnosis_update.\
                                    get('diagnosis_lab_facility_id', '')
                                diagnosis_test_lab_serial_number = diagnosis_update.\
                                    get('diagnosis_test_lab_serial_number', '')
                                diagnosis_test_summary = diagnosis_update.\
                                    get('diagnosis_test_summary', '')
                                diagnosis_test_type = diagnosis_update.\
                                    get('diagnosis_test_type', '')
                                diagnosis_test_type_label = diagnosis_update.\
                                    get('diagnosis_test_type_label', '')
                                datamigration_diagnosis_test_information2 = 'yes'

                    if datamigration_diagnosis_test_information2 == "yes":
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
                        datamigration_diagnosis_test_information,
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
                        flag_for_review,
                        datamigration_diagnosis_test_information2,
                    ])

        print('Migration complete at {}'.format(datetime.utcnow()))

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
    def get_relevant_test_case(domain, episode_case, test_confirming_diagnosis):
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
            and case.get_case_property('test_type_value') == test_confirming_diagnosis
        ]

        if test_cases:
            return sorted(test_cases, key=lambda c: c.get_case_property('date_reported'))[-1]
        else:
            return None

    @staticmethod
    def _get_diagnosis_update(episode):
        """get first form that set diagnosis_test_type to a value """
        for action in episode.actions:
            if action.form is not None:
                for update in get_case_updates(action.form):
                    if (
                        update.id == episode.case_id
                        and update.get_update_action()
                        and update.get_update_action().dynamic_properties.get('diagnosis_test_type', '')
                    ):
                        return update
