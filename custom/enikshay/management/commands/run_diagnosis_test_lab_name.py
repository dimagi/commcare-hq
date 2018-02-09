from __future__ import print_function

from __future__ import absolute_import
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.management.commands.utils import (
    BaseEnikshayCaseMigration,
)
from custom.enikshay.case_utils import get_occurrence_case_from_episode, ENikshayCaseNotFound


class Command(BaseEnikshayCaseMigration):
    case_type = 'episode'
    case_properties_to_update = [
        'diagnosis_lab_facility_name',
    ]
    datamigration_case_property = 'datamigration_diagnosis_test_lab_name'
    include_public_cases = True
    include_private_cases = False

    @staticmethod
    def get_case_property_updates(episode, domain):
        if (
            episode.get_case_property('datamigration_diagnosis_test_lab_name') != 'yes'
            and episode.get_case_property('episode_type') == 'confirmed_tb'
            and episode.get_case_property('diagnosis_test_result_date')
            and not episode.get_case_property('diagnosis_lab_facility_name')
        ):
            test = Command.get_relevant_test_case(domain, episode)
            if test:
                diagnosis_lab_facility_name = test.get_case_property('testing_facility_name')
                if diagnosis_lab_facility_name:
                    return {'diagnosis_lab_facility_name': diagnosis_lab_facility_name}
        return {}

    @staticmethod
    def get_relevant_test_case(domain, episode_case):
        try:
            occurrence_case = get_occurrence_case_from_episode(domain, episode_case.case_id)
        except ENikshayCaseNotFound:
            return None

        indexed_cases = CaseAccessors(domain).get_reverse_indexed_cases([occurrence_case.case_id])
        test_cases = [
            case for case in indexed_cases if (
                case.type == 'test'
                and case.get_case_property('rft_general') == 'diagnosis_dstb'
                and case.get_case_property('result') == 'tb_detected'
            )
        ]
        if test_cases:
            return sorted(test_cases, key=lambda c: c.get_case_property('date_reported'))[-1]
        else:
            return None
