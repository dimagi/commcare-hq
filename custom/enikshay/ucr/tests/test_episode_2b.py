import json
import os

import mock
from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext
from corehq.apps.userreports.expressions.factory import SubcasesExpressionSpec

EPISODE_DATA_SOURCE = 'episode_2b_v4.json'


class TestEpisode2B(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestEpisode2B, cls).setUpClass()

        episode_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'data_sources',
            EPISODE_DATA_SOURCE
        )

        with open(episode_file) as f:
            cls.episode = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.episode.named_expression_objects

    def setUp(self):
        self.orig_db = CommCareCase.get_db()
        self.database = FakeCouchDb()
        CommCareCase.set_db(self.database)

    def tearDown(self):
        CommCareCase.set_db(self.orig_db)

    def _get_column(self, column_id):
        return [
            ind
            for ind in self.episode.configured_indicators
            if ind['column_id'] == column_id
        ][0]

    def test_treating_phi_property_when_clause_true(self):
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

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'owner-id')

    def test_treating_phi_property_when_clause_treatment_initiation_date_is_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': None,
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

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_treating_phi_property_when_clause_archive_reason_is_not_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': 'test',
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

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_treating_phi_property_when_clause_treatment_outcome_is_not_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_tu_name_property_when_clause_true(self):
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
            ]
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'tu_name': 'test'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        column = self._get_column('tu_name')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'test')

    def test_tu_name_property_when_clause_treatment_initiation_date_is_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': None,
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
            ]
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'owner_id': 'owner-id',
            'tu_name': 'test'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_tu_name_property_when_clause_archive_reason_is_not_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': 'test',
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
            ]
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'owner_id': 'owner-id',
            'tu_name': 'test'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_tu_name_property_when_clause_treatment_outcome_is_not_null(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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
            'owner_id': 'owner-id',
            'tu_name': 'test'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        column = self._get_column('treating_phi')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertIsNone(expression(episode_case, EvaluationContext(episode_case, 0)))

    def test_microbiological_properties(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        subcases = [
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_ip',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
                'result_recorded': 'yes'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
                'result_recorded': 'yes'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
            }
        ]

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        column = self._get_column('endofip_test_requested_date')
        self.assertEqual(column['datatype'], 'date')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        column2 = self._get_column('endofcp_test_requested_date')
        self.assertEqual(column2['datatype'], 'date')
        expression2 = ExpressionFactory.from_spec(
            column2['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(SubcasesExpressionSpec, '__call__', lambda *args: subcases):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), '2017-09-28')
            self.assertEqual(expression2(episode_case, EvaluationContext(episode_case, 0)), '2017-09-28')

    def test_microbiological_properties_when_clause_is_false(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        subcases = [
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_ip',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'not-microscopy'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'not-microscopy',
                'result_recorded': 'yes'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
            }
        ]

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        endofip_test_requested_date = self._get_column('endofip_test_requested_date')
        self.assertEqual(endofip_test_requested_date['datatype'], 'date')
        endofip_test_requested_date_expression = ExpressionFactory.from_spec(
            endofip_test_requested_date['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        endofcp_test_requested_date = self._get_column('endofcp_test_requested_date')
        self.assertEqual(endofcp_test_requested_date['datatype'], 'date')
        endofcp_test_requested_date_expression = ExpressionFactory.from_spec(
            endofcp_test_requested_date['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(SubcasesExpressionSpec, '__call__', lambda *args: subcases):
            self.assertIsNone(
                endofip_test_requested_date_expression(episode_case, EvaluationContext(episode_case, 0))
            )
            self.assertIsNone(
                endofcp_test_requested_date_expression(episode_case, EvaluationContext(episode_case, 0))
            )

    def test_microbiological_endofip_test_requested_date(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        subcases = [
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'no',
                'rft_dstb_followup': 'end_of_ip',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-08-10',
                'test_type_value': 'microscopy-zn',
                'result_recorded': 'yes'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'yes',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-08-10',
                'test_type_value': 'microscopy-zn',
                'result_recorded': 'yes'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
            }
        ]

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        endofip_test_requested_date = self._get_column('endofip_test_requested_date')
        self.assertEqual(endofip_test_requested_date['datatype'], 'date')
        endofip_test_requested_date_expression = ExpressionFactory.from_spec(
            endofip_test_requested_date['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        endofcp_test_requested_date = self._get_column('endofcp_test_requested_date')
        self.assertEqual(endofcp_test_requested_date['datatype'], 'date')
        endofcp_test_requested_date_expression = ExpressionFactory.from_spec(
            endofcp_test_requested_date['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(SubcasesExpressionSpec, '__call__', lambda *args: subcases):
            self.assertEqual(
                endofip_test_requested_date_expression(episode_case, EvaluationContext(episode_case, 0)),
                '2017-09-28'
            )
            self.assertEqual(
                endofcp_test_requested_date_expression(episode_case, EvaluationContext(episode_case, 0)),
                '2017-08-10'
            )

    def test_microbiological_endofip_result_smear(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        subcases = [
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'no',
                'rft_dstb_followup': 'end_of_ip',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-08-10',
                'test_type_value': 'microscopy-zn',
                'result_grade': 'result_grade',
                'result_recorded': 'yes',
                'result_summary_display': 'result'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'yes',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-08-10',
                'test_type_value': 'cbnaat',
                'result': 'result',
                'result_recorded': 'yes',
                'result_summary_display': 'result'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'test_type_value': 'microscopy-zn',
            }
        ]

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        endofip_result = self._get_column('endofip_result')
        self.assertEqual(endofip_result['datatype'], 'string')
        endofip_result_expression = ExpressionFactory.from_spec(
            endofip_result['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        endofcp_result = self._get_column('endofcp_result')
        self.assertEqual(endofcp_result['datatype'], 'string')
        endofcp_result_expression = ExpressionFactory.from_spec(
            endofcp_result['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(SubcasesExpressionSpec, '__call__', lambda *args: subcases):
            self.assertEqual(
                endofip_result_expression(episode_case, EvaluationContext(episode_case, 0)),
                'result'
            )
            self.assertEqual(
                endofcp_result_expression(episode_case, EvaluationContext(episode_case, 0)),
                'result'
            )

    def test_not_microbiological_result(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
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

        subcases = [
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'no',
                'rft_dstb_followup': 'end_of_ip',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-08-10',
                'date_reported': '2017-08-10',
                'test_type_value': 'cytopathology',
                'result_grade': 'result_grade',
                'result_recorded': 'yes',
                'result_summary_display': 'result_cytopathology'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'is_direct_test_entry': 'yes',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-09-28',
                'date_tested': '2017-09-10',
                'date_reported': '2017-09-10',
                'test_type_value': 'igra',
                'result': 'result',
                'result_recorded': 'yes',
                'result_summary_display': 'result_igra'
            },
            {
                'domain': 'enikshay-test',
                'type': 'test',
                'rft_dstb_followup': 'end_of_cp',
                'test_requested_date': '2017-10-10',
                'date_reported': '2017-10-10',
                'test_type_value': 'other_clinical',
                'result_summary_display': 'result_other_clinical'
            }
        ]

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case
        }

        not_microbiological = self._get_column('not_microbiological_result')
        self.assertEqual(not_microbiological['datatype'], 'string')
        not_microbiological_result_expression = ExpressionFactory.from_spec(
            not_microbiological['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(SubcasesExpressionSpec, '__call__', lambda *args: subcases):
            self.assertEqual(
                not_microbiological_result_expression(episode_case, EvaluationContext(episode_case, 0)),
                'result_cytopathology'
            )

    def test_disease_classification_pulmonary(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'disease_classification': 'pulmonary',
            'site_choice': 'Other',
            'site_detail': 'test detail',
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

        column = self._get_column('disease_classification')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'Pulmonary')

    def test_disease_classification_extra_pulmonary_site_choice_not_other(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'disease_classification': 'extra_pulmonary',
            'site_choice': 'test',
            'site_detail': 'test detail',
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

        column = self._get_column('disease_classification')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'Extra Pulmonary, test')

    def test_disease_classification_extra_pulmonary_site_choice_other(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': 'test',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'disease_classification': 'extra_pulmonary',
            'site_choice': 'Other',
            'site_detail': 'test detail',
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

        column = self._get_column('disease_classification')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(
            expression(episode_case, EvaluationContext(episode_case, 0)),
            'Extra Pulmonary, Other, test detail'
        )
