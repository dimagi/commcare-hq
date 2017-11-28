from __future__ import absolute_import
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

TEST_DATA_SOURCE = 'test_2b_v5.json'


class TestTestCase2B(TestDataSourceExpressions):

    data_source_name = TEST_DATA_SOURCE

    def test_follow_up_treatment_initiation_date_month_follow_up_dstb(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-07-01',
            'archive_reason': None,
            'treatment_outcome': None,
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_dstb',
            'rft_dstb_follow_up_treatment_month': '3',
            'date_reported': '2017-10-01'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'test_case_id': test_case
        }

        expression = self.get_expression('follow_up_treatment_initiation_date_month', 'string')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), '3')

    def test_follow_up_treatment_initiation_date_month_follow_up_drtb(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-07-01',
            'archive_reason': None,
            'treatment_outcome': None,
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_drtb',
            'date_reported': '2017-10-01',
            'rft_drtb_follow_up_treatment_month': '6'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'test_case_id': test_case
        }

        expression = self.get_expression('follow_up_treatment_initiation_date_month', 'string')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), '6')

    def test_key_populations(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': None,
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'indices': [
                {'referenced_id': 'person_case_id'}
            ],
            'key_populations': 'test test2 test3'
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'owner_id': 'owner-id'
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_dstb',
            'date_reported': '2017-10-01',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case,
            'test_case_id': test_case
        }

        expression = self.get_expression('key_populations', 'string')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 'test, test2, test3')

    def test_dmc_referring_facility_id(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'referring_facility_id': 'facility_id',
        }

        expression = self.get_expression('dmc_referring_facility_id', 'string')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 'facility_id')

    def test_presumptives_examined_for_diagnosis(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_type_at_request': 'presumptive_tb',
            'rft_general': 'diagnosis_dstb'
        }

        expression = self.get_expression('presumptives_examined_for_diagnosis', 'integer')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['rft_general'] = 'diagnosis_drtb'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['episode_type_at_request'] = 'other type'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_presumptives_found_positive(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_type_at_request': 'presumptive_tb',
            'rft_general': 'diagnosis_dstb',
            'result': 'tb_detected'
        }

        expression = self.get_expression('presumptives_found_positive', 'integer')

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['rft_general'] = 'diagnosis_drtb'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['result'] = 'other'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

        test_case['episode_type_at_request'] = 'other type'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_follow_up_patients_examined(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_type_at_request': 'confirmed_tb',
            'rft_general': 'follow_up_dstb'
        }

        expression = self.get_expression('follow_up_patients_examined', 'integer')
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['episode_type_at_request'] = 'confirmed_drtb'
        test_case['rft_general'] = 'follow_up_drtb'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['rft_general'] = 'diagnosis_drtb'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

        test_case['episode_type_at_request'] = 'other type'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_patients_positive_on_follow_up(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_type_at_request': 'confirmed_tb',
            'rft_general': 'follow_up_dstb',
            'result': 'tb_detected'
        }

        expression = self.get_expression('patients_positive_on_follow_up', 'integer')
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['episode_type_at_request'] = 'confirmed_drtb'
        test_case['rft_general'] = 'follow_up_drtb'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['result'] = 'other resault'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

        test_case['episode_type_at_request'] = 'other type'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_slides_examined(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'microscopy_sample_a_result': 'scanty',
            'microscopy_sample_b_result': 'negative_not_seen',
        }

        expression = self.get_expression('slides_examined', 'integer')
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 2)

        test_case['microscopy_sample_a_result'] = ''
        test_case['microscopy_sample_b_result'] = 'negative_not_seen'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = 'scanty'
        test_case['microscopy_sample_b_result'] = ''
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = ''
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_positive_slides(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'microscopy_sample_a_result': 'scanty',
            'microscopy_sample_b_result': '1plus',
        }

        expression = self.get_expression('positive_slides', 'integer')
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 2)

        test_case['microscopy_sample_a_result'] = 'negative_not_seen'
        test_case['microscopy_sample_b_result'] = '1plus'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = 'scanty'
        test_case['microscopy_sample_b_result'] = ''
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = ''
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

    def test_negative_slides(self):
        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'microscopy_sample_a_result': 'scanty',
            'microscopy_sample_b_result': '1plus',
        }

        expression = self.get_expression('negative_slides', 'integer')
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 0)

        test_case['microscopy_sample_a_result'] = 'negative_not_seen'
        test_case['microscopy_sample_b_result'] = '1plus'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = 'scanty'
        test_case['microscopy_sample_b_result'] = 'negative_not_seen'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 1)

        test_case['microscopy_sample_a_result'] = 'negative_not_seen'
        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 2)
