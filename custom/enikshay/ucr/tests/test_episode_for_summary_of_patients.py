from corehq.apps.userreports.specs import EvaluationContext
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

DATA_SOURCE = 'episode_for_summary_of_patients.json'


class TestEpisodeForSummaryOfPatients(TestDataSourceExpressions):

    data_source_name = DATA_SOURCE

    def test_date_of_diagnosis(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'date_of_diagnosis': '2017-10-01',
        }

        date_of_diagnosis = self.get_expression('date_of_diagnosis', 'date')

        self.assertEqual(
            date_of_diagnosis(episode_case, EvaluationContext(episode_case, 0)),
            '2017-10-01'
        )

    def test_person_id(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'indices': [
                {'referenced_id': 'person_case_id'}
            ]
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'owner_id': 'owner-id'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        person_id = self.get_expression('person_owner_id', 'string')
        self.assertEqual(
            person_id(episode_case, EvaluationContext(episode_case, 0)),
            'owner-id'
        )

    def test_diagnosing_facility_id(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'diagnosing_facility_id': 'facility_id',
        }

        date_of_diagnosis = self.get_expression('diagnosing_facility_id', 'string')

        self.assertEqual(
            date_of_diagnosis(episode_case, EvaluationContext(episode_case, 0)),
            'facility_id'
        )

    def test_confirmed_tb(self):
        episode_case_tb = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_tb'
        }
        episode_case_drtb = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_drtb'
        }

        confirmed_tb = self.get_expression('confirmed_tb', 'integer')

        self.assertEqual(
            confirmed_tb(episode_case_tb, EvaluationContext(episode_case_tb, 0)),
            1
        )
        self.assertEqual(
            confirmed_tb(episode_case_drtb, EvaluationContext(episode_case_drtb, 0)),
            0
        )

    def test_confirmed_drtb(self):
        episode_case_tb = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_tb'
        }
        episode_case_drtb = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_drtb'
        }

        confirmed_tb = self.get_expression('confirmed_drtb', 'integer')

        self.assertEqual(
            confirmed_tb(episode_case_tb, EvaluationContext(episode_case_tb, 0)),
            0
        )
        self.assertEqual(
            confirmed_tb(episode_case_drtb, EvaluationContext(episode_case_drtb, 0)),
            1
        )

    def test_drtb_patients_on_treatment(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_drtb',
            'treatment_initiation_date': '2017-10-01'
        }

        drtb_patients_on_treatment = self.get_expression('drtb_patients_on_treatment', 'integer')

        self.assertEqual(
            drtb_patients_on_treatment(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        episode_case['episode_type'] = 'confirmed_tb'
        self.assertEqual(
            drtb_patients_on_treatment(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['episode_type'] = 'confirmed_drtb'
        episode_case['treatment_initiation_date'] = ''
        self.assertEqual(
            drtb_patients_on_treatment(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['episode_type'] = 'confirmed_tb'
        episode_case['treatment_initiation_date'] = None
        self.assertEqual(
            drtb_patients_on_treatment(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

    def test_patients_on_ip(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'episode_type': 'confirmed_tb',
            'treatment_initiation_date': '2017-10-01',
            'cp_initiated': 'no'
        }

        patients_on_ip = self.get_expression('patients_on_ip', 'integer')

        self.assertEqual(
            patients_on_ip(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        episode_case.update({
            'episode_type': 'confirmed_drtb',
            'treatment_initiation_date': '2017-10-01',
            'cp_initiated': 'no'
        })
        self.assertEqual(
            patients_on_ip(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case.update({
            'episode_type': 'confirmed_drtb',
            'treatment_initiation_date': None,
            'cp_initiated': 'yes'
        })
        self.assertEqual(
            patients_on_ip(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case.update({
            'episode_type': 'confirmed_drtb',
            'treatment_initiation_date': '2017-10-01',
            'cp_initiated': 'yes'
        })
        self.assertEqual(
            patients_on_ip(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

    def test_patients_on_cp(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'cp_initiated': 'yes'
        }

        patients_on_cp = self.get_expression('patients_on_cp', 'integer')

        self.assertEqual(
            patients_on_cp(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        episode_case['cp_initiated'] = 'no'
        self.assertEqual(
            patients_on_cp(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

    def test_treatment_outcome(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_outcome': 'test_value'
        }

        treatment_outcome = self.get_expression('treatment_outcome', 'integer')

        self.assertEqual(
            treatment_outcome(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        episode_case['treatment_outcome'] = ''
        self.assertEqual(
            treatment_outcome(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

    def test_weight_band(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'weight_band': ''
        }

        weight_band_adult = self.get_expression('weight_band_adult_25_39', 'integer')

        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = 'adult_25-39'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_adult_40_54', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = 'adult_40-54'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_adult_55_69', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = 'adult_55-69'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_adult_gt_70', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = 'adult_greater_than_70'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_11_17', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = '11-17'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_18_25', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = '18-25'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_26_30', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = '26-30'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

        weight_band_adult = self.get_expression('weight_band_31_60', 'integer')
        episode_case['weight_band'] = ''
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            0
        )

        episode_case['weight_band'] = '31-60'
        self.assertEqual(
            weight_band_adult(episode_case, EvaluationContext(episode_case, 0)),
            1
        )

