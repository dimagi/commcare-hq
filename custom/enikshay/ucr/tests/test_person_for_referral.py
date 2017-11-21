from __future__ import absolute_import

import mock

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

from custom.enikshay.expressions import EpisodeFromPersonExpression


class TestPersonForReferralDataSource(TestDataSourceExpressions):

    data_source_name = 'person_for_referral_report_v2.json'

    def test_regimen_property_confirmed_drtb(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        episode_case = {
            '_id': 'episode-case-id',
            'adherence_schedule_id': '',
            'case_definition': '',
            'date_of_diagnosis': '',
            'domain': 'enikshay-test',
            'enikshay_enabled': '',
            'episode_type': 'confirmed_drtb',
            'patient_type_choice': '',
            'treatment_regimen': 'test_regimen'
        }

        self.database.mock_docs = {
            'episode-case-id': episode_case,
            'person-case-id': person_case
        }

        column = self.get_column('regimen')
        self.assertEqual(column['datatype'], 'string')

        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(EpisodeFromPersonExpression, '__call__', lambda *args: episode_case):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'test_regimen')

    def test_regimen_property_confirmed_tb(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        episode_case = {
            '_id': 'episode-case-id',
            'adherence_schedule_id': '',
            'case_definition': '',
            'date_of_diagnosis': '',
            'domain': 'enikshay-test',
            'enikshay_enabled': '',
            'episode_type': 'confirmed_tb',
            'patient_type_choice': 'new',
            'treatment_regimen': 'test_regimen'
        }

        self.database.mock_docs = {
            'episode-case-id': episode_case,
            'person-case-id': person_case
        }

        column = self.get_column('regimen')
        self.assertEqual(column['datatype'], 'string')

        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(EpisodeFromPersonExpression, '__call__', lambda *args: episode_case):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'New')

    def test_regimen_property_private_treatment(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        episode_case = {
            '_id': 'episode-case-id',
            'adherence_schedule_id': '',
            'case_definition': '',
            'date_of_diagnosis': '',
            'domain': 'enikshay-test',
            'enikshay_enabled': '',
            'episode_type': 'confirmed_tb',
            'patient_type_choice': 'not_new',
            'treatment_regimen': 'test_regimen',
            'treatment_status': 'yes_private'
        }

        self.database.mock_docs = {
            'episode-case-id': episode_case,
            'person-case-id': person_case
        }

        column = self.get_column('regimen')
        self.assertEqual(column['datatype'], 'string')

        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(EpisodeFromPersonExpression, '__call__', lambda *args: episode_case):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'Outisde RNTCP')

    def test_regimen_property_previously_treated(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        episode_case = {
            '_id': 'episode-case-id',
            'adherence_schedule_id': '',
            'case_definition': '',
            'date_of_diagnosis': '',
            'domain': 'enikshay-test',
            'enikshay_enabled': '',
            'episode_type': 'confirmed_tb',
            'patient_type_choice': 'other_previously_treated',
            'treatment_regimen': 'test_regimen',
            'treatment_status': ''
        }

        self.database.mock_docs = {
            'episode-case-id': episode_case,
            'person-case-id': person_case
        }

        column = self.get_column('regimen')
        self.assertEqual(column['datatype'], 'string')

        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        with mock.patch.object(EpisodeFromPersonExpression, '__call__', lambda *args: episode_case):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'Previously Treated')
