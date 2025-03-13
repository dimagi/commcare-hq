from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.integration.payments.services import verify_payment_cases
from corehq.apps.integration.payments.const import PaymentProperties


class TestVerifyPaymentCases(TestCase):

    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.username = 'test-user'
        cls.password = '1234'
        cls.webuser = WebUser.create(
            cls.domain,
            cls.username,
            cls.password,
            None,
            None,
            is_admin=True,
        )
        cls.webuser.save()

        factory = CaseFactory(cls.domain)
        cls.case_list = [
            _create_case(
                factory,
                name='foo',
                data={
                    'batch_number': 'B001',
                    'email': 'bsmith@example.org',
                    'phone_number': '0987654321',
                    'amount': '100',
                    'currency': 'Dollar',
                    'payee_note': 'Jan payment',
                    'payer_message': 'Thanks',
                }),
            _create_case(
                factory,
                name='bar',
                data={
                    'batch_number': 'B001',
                    'phone_number': '0987654322',
                }),
        ]

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        for case in cls.case_list:
            case.delete()

        super().tearDownClass()

    def test_verify_payment_cases(self):
        for case in self.case_list:
            assert PaymentProperties.PAYMENT_VERIFIED not in case.case_json

        case_ids = [case_.case_id for case_ in self.case_list]
        verified_cases = verify_payment_cases(self.domain, case_ids, self.webuser)

        assert len(verified_cases) == 2

        for case in self.case_list:
            case.refresh_from_db()
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED] == 'True'
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_BY] == self.webuser.username
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID] == self.webuser.user_id
            assert case.case_json[PaymentProperties.PAYMENT_VERIFIED_ON_UTC] is not None


def _create_case(factory, name, data):
    return factory.create_case(
        case_name=name,
        case_type=MOMO_PAYMENT_CASE_TYPE,
        update=data
    )
