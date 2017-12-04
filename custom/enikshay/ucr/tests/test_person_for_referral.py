from __future__ import absolute_import

import mock

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

from custom.enikshay.expressions import MostRecentEpisodeCaseFromPerson, MostRecentReferralCaseFromPerson


class TestPersonForReferralDataSource(TestDataSourceExpressions):

    data_source_name = 'person_for_referral_report_v3.json'

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

        with mock.patch.object(MostRecentEpisodeCaseFromPerson, '__call__', lambda *args: episode_case):
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

        with mock.patch.object(MostRecentEpisodeCaseFromPerson, '__call__', lambda *args: episode_case):
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

        with mock.patch.object(MostRecentEpisodeCaseFromPerson, '__call__', lambda *args: episode_case):
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

        with mock.patch.object(MostRecentEpisodeCaseFromPerson, '__call__', lambda *args: episode_case):
            self.assertEqual(expression(episode_case, EvaluationContext(episode_case, 0)), 'Previously Treated')

    def test_person_properties(self):
        person_case = {
            '_id': 'person-case-id',
            'name': 'person name',
            'dob': '2017-01-01',
            'sex': 'female',
            'age': 'some age',
            'phone_number': '12345678',
            'current_patient_type_choice': 'test choice',
            'person_id': 'person ID',
            'current_address': 'address',
        }

        name = self.get_expression('name', 'string')
        dob = self.get_expression('dob', 'date')
        sex = self.get_expression('sex', 'string')
        age = self.get_expression('age', 'string')
        phone_number = self.get_expression('phone_number', 'string')
        current_patient_type_choice = self.get_expression('current_patient_type_choice', 'string')
        enikshay_id = self.get_expression('enikshay_id', 'string')
        current_address = self.get_expression('address', 'string')

        self.assertEqual(name(person_case, EvaluationContext(person_case, 0)), 'person name')
        self.assertEqual(dob(person_case, EvaluationContext(person_case, 0)), '2017-01-01')
        self.assertEqual(sex(person_case, EvaluationContext(person_case, 0)), 'female')
        self.assertEqual(age(person_case, EvaluationContext(person_case, 0)), 'some age')
        self.assertEqual(phone_number(person_case, EvaluationContext(person_case, 0)), '12345678')
        self.assertEqual(
            current_patient_type_choice(person_case, EvaluationContext(person_case, 0)),
            'test choice'
        )
        self.assertEqual(enikshay_id(person_case, EvaluationContext(person_case, 0)), 'person ID')
        self.assertEqual(current_address(person_case, EvaluationContext(person_case, 0)), 'address')

    def test_referrer_properties(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        referrer_case = {
            '_id': 'referrer-case-id',
            'owner_id': 'owner',
            'referral_initiated_date': '2017-12-01',
            'referral_closed_date': '2017-12-30',
            'location_type': 'sto',
            'location_id': 'location_id'
        }

        self.database.mock_docs = {
            'referrer-case-id': referrer_case,
            'person-case-id': person_case
        }

        referred_to = self.get_expression('referred_to', 'string')
        date_of_referral = self.get_expression('date_of_referral', 'date')
        date_of_acceptance = self.get_expression('date_of_acceptance', 'date')

        with mock.patch.object(MostRecentReferralCaseFromPerson, '__call__', lambda *args: referrer_case):
            self.assertEqual(referred_to(person_case, EvaluationContext(person_case, 0)), 'owner')
            self.assertEqual(date_of_referral(person_case, EvaluationContext(person_case, 0)), '2017-12-01')
            self.assertEqual(date_of_acceptance(person_case, EvaluationContext(person_case, 0)), '2017-12-30')

    def test_episode_properties(self):
        person_case = {
            '_id': 'person-case-id',
            'domain': 'enikshay-test',
        }

        episode_case = {
            '_id': 'episode-case-id',
            'treatment_initiated': 'yes_phi',
            'nikshay_id': 'some nikshay id',
            'case_definition': 'test definition',
            'date_of_diagnosis': '2017-10-01',
            'episode_type': 'type_of_episode',
            'adherence_schedule_id': 'schedule_id',
            'enikshay_enabled': 'enabled'
        }

        self.database.mock_docs = {
            'episode-case-id': episode_case,
            'person-case-id': person_case
        }

        treatment_initiated = self.get_expression('treatment_initiated', 'string')
        nikshay_id = self.get_expression('nikshay_id', 'string')
        case_definition = self.get_expression('case_definition', 'string')
        date_of_diagnosis = self.get_expression('date_of_diagnosis', 'date')
        episode_type = self.get_expression('episode_type', 'string')
        adherence_schedule_id = self.get_expression('adherence_schedule_id', 'string')
        enikshay_enabled = self.get_expression('enikshay_enabled', 'string')

        with mock.patch.object(MostRecentEpisodeCaseFromPerson, '__call__', lambda *args: episode_case):
            self.assertEqual(treatment_initiated(person_case, EvaluationContext(person_case, 0)), 'Yes')
            self.assertEqual(nikshay_id(person_case, EvaluationContext(person_case, 0)), 'some nikshay id')
            self.assertEqual(case_definition(person_case, EvaluationContext(person_case, 0)), 'test definition')
            self.assertEqual(date_of_diagnosis(person_case, EvaluationContext(person_case, 0)), '2017-10-01')
            self.assertEqual(episode_type(person_case, EvaluationContext(person_case, 0)), 'type_of_episode')
            self.assertEqual(
                adherence_schedule_id(person_case, EvaluationContext(person_case, 0)),
                'schedule_id'
            )
            self.assertEqual(enikshay_enabled(person_case, EvaluationContext(person_case, 0)), 'enabled')
