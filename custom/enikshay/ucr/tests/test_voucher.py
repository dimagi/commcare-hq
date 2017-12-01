from __future__ import absolute_import

import mock

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext
from corehq.apps.userreports.expressions.factory import SubcasesExpressionSpec
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from custom.enikshay.expressions import FirstCaseFormWithXmlns
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

VOUCHER_DATA_SOURCE = 'voucher_v4.json'


class TestVoucher(TestDataSourceExpressions):

    data_source_name = VOUCHER_DATA_SOURCE

    def test_voucher_properties(self):
        voucher_case = {
            '_id': 'voucher_case_id',
            'domain': 'enikshay-test',
            'date_fulfilled': '2017-09-28',
            'voucher_issued_by_login_name': 'login_name',
            'voucher_issued_by_name': 'name',
            'voucher_issued_by_phone_number': '123456',
            'voucher_id': 'voucher_case_id',
            'date_issued': '2017-09-28',
            'state': 'test_state',
            'amount_fulfilled': '123',
            'voucher_fulfilled_by_login_name': 'fulfilled_login_name',
            'voucher_fulfilled_by_name': 'fulfilled_name',
            'voucher_fulfilled_by_phone_number': '654321',
            'investigation_type_name': 'type'

        }

        date_fulfilled = self.get_expression('date_fulfilled', 'date')
        voucher_issued_by_login_name = self.get_expression('voucher_issued_by_login_name', 'string')
        voucher_issued_by_name = self.get_expression('voucher_issued_by_name', 'string')
        voucher_issued_by_phone_number = self.get_expression('voucher_issued_by_phone_number', 'string')
        voucher_id = self.get_expression('voucher_id', 'string')
        date_issued = self.get_expression('date_issued', 'date')
        state = self.get_expression('state', 'string')
        amount_fulfilled = self.get_expression('amount_fulfilled', 'integer')
        voucher_fulfilled_by_login_name = self.get_expression('voucher_fulfilled_by_login_name', 'string')
        voucher_fulfilled_by_name = self.get_expression('voucher_fulfilled_by_name', 'string')
        voucher_fulfilled_by_phone_number = self.get_expression('voucher_fulfilled_by_phone_number', 'string')
        investigation_type_name = self.get_expression('investigation_type_name', 'string')

        self.assertEqual(
            date_fulfilled(voucher_case, EvaluationContext(voucher_case, 0)),
            '2017-09-28'
        )
        self.assertEqual(
            voucher_issued_by_login_name(voucher_case, EvaluationContext(voucher_case, 0)),
            'login_name'
        )
        self.assertEqual(
            voucher_issued_by_name(voucher_case, EvaluationContext(voucher_case, 0)),
            'name'
        )
        self.assertEqual(
            voucher_issued_by_phone_number(voucher_case, EvaluationContext(voucher_case, 0)),
            '123456'
        )
        self.assertEqual(
            voucher_id(voucher_case, EvaluationContext(voucher_case, 0)),
            'voucher_case_id'
        )
        self.assertEqual(
            date_issued(voucher_case, EvaluationContext(voucher_case, 0)),
            '2017-09-28'
        )
        self.assertEqual(
            state(voucher_case, EvaluationContext(voucher_case, 0)),
            'test_state'
        )
        self.assertEqual(
            amount_fulfilled(voucher_case, EvaluationContext(voucher_case, 0)),
            '123'
        )
        self.assertEqual(
            voucher_fulfilled_by_login_name(voucher_case, EvaluationContext(voucher_case, 0)),
            'fulfilled_login_name'
        )
        self.assertEqual(
            voucher_fulfilled_by_name(voucher_case, EvaluationContext(voucher_case, 0)),
            'fulfilled_name'
        )
        self.assertEqual(
            voucher_fulfilled_by_phone_number(voucher_case, EvaluationContext(voucher_case, 0)),
            '654321'
        )
        self.assertEqual(
            investigation_type_name(voucher_case, EvaluationContext(voucher_case, 0)),
            'type'
        )

    def test_person_properties(self):
        voucher_case = {
            '_id': 'voucher_case_id',
            'domain': 'enikshay-test',
            'date_fulfilled': '2017-09-28',
            'voucher_type': 'test',
        }

        person_case = {
            '_id': 'person_case_id',
            'person_id': 'person_case_id',
            'name': 'test_name',
            'domain': 'enikshay-test',
            'phone_number': '123432',
            'owner_id': 'owner-id',
            'date_of_registration': '2017-09-28',
            'private_sector_organization_name': 'organization_name'
        }

        investigation_form = {
            "_id": 'investigation_form_id',
            "domain": "enikshay-test",
            "form": {
                "beneficiary_data": {
                    "person_id": "person_case_id",
                }
            },
            "xmlns": "http://openrosa.org/formdesigner/f710654022ff2d0653b315b71903257dbf53249b",
        }

        self.database.mock_docs = {
            'voucher_case_id': voucher_case,
            'person_case_id': person_case,
            'investigation_form_id': investigation_form
        }
        person_owner_id = self.get_expression('person_owner_id', 'string')
        private_sector_organization_name = self.get_expression('private_sector_organization_name', 'string')
        person_id = self.get_expression('person_id', 'string')
        person_name = self.get_expression('name', 'string')
        phone_number = self.get_expression('phone_number', 'string')
        date_of_registration = self.get_expression('date_of_registration', 'date')
        with mock.patch.object(FirstCaseFormWithXmlns, '__call__', return_value=investigation_form):
            self.assertEqual(
                person_owner_id(voucher_case, EvaluationContext(voucher_case, 0)),
                'owner-id'
            )
            self.assertEqual(
                private_sector_organization_name(voucher_case, EvaluationContext(voucher_case, 0)),
                'organization_name'
            )
            self.assertEqual(
                person_id(voucher_case, EvaluationContext(voucher_case, 0)),
                'person_case_id'
            )
            self.assertEqual(
                person_name(voucher_case, EvaluationContext(voucher_case, 0)),
                'test_name'
            )
            self.assertEqual(
                phone_number(voucher_case, EvaluationContext(voucher_case, 0)),
                '123432'
            )
            self.assertEqual(
                date_of_registration(voucher_case, EvaluationContext(voucher_case, 0)),
                '2017-09-28'
            )

    def test_episode_properties(self):
        voucher_case = {
            '_id': 'voucher_case_id',
            'domain': 'enikshay-test',
            'date_fulfilled': '2017-09-28',
            'voucher_type': 'test',
        }

        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'episode_type': 'test_episode'
        }

        person_case = {
            '_id': 'person_case_id',
            'person_id': 'person_case_id',
            'name': 'test_name',
            'domain': 'enikshay-test',
            'phone_number': '123432',
            'owner_id': 'owner-id',
            'date_of_registration': '2017-09-28',
            'private_sector_organization_name': 'organization_name'
        }

        investigation_form = {
            "_id": 'investigation_form_id',
            "domain": "enikshay-test",
            "form": {
                "beneficiary_data": {
                    "episode_id": "episode_case_id",
                    "person_id": "person_case_id",
                }
            },
            "xmlns": "http://openrosa.org/formdesigner/f710654022ff2d0653b315b71903257dbf53249b",
        }

        self.database.mock_docs = {
            'voucher_case_id': voucher_case,
            'person_case_id': person_case,
            'episode_case_id': episode_case,
            'investigation_form_id': investigation_form
        }
        episode_type = self.get_expression('episode_type', 'string')
        with mock.patch.object(FirstCaseFormWithXmlns, '__call__', return_value=investigation_form):
            self.assertEqual(
                episode_type(voucher_case, EvaluationContext(voucher_case, 0)),
                'test_episode'
            )

    def test_test_properties(self):
        voucher_case = {
            '_id': 'voucher_case_id',
            'domain': 'enikshay-test',
            'date_fulfilled': '2017-09-28',
            'voucher_type': 'test',
            'indices': [
                {'referenced_id': 'test_case_id'}
            ]
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'purpose_of_test': 'diagnosis',
            'date_reported': '2017-09-28',
            'case_id': 'case ID'
        }

        self.database.mock_docs = {
            'voucher_case_id': voucher_case,
            'test_case_id': test_case,
        }

        purpose_of_test = self.get_expression('purpose_of_test', 'string')
        date_reported = self.get_expression('date_reported', 'date')
        test_id = self.get_expression('test_id', 'string')
        self.assertEqual(
            purpose_of_test(voucher_case, EvaluationContext(voucher_case, 0)),
            'diagnosis'
        )
        self.assertEqual(
            date_reported(voucher_case, EvaluationContext(voucher_case, 0)),
            '2017-09-28'
        )
        self.assertEqual(
            test_id(voucher_case, EvaluationContext(voucher_case, 0)),
            'case ID'
        )
