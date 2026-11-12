from types import SimpleNamespace

from django.test import SimpleTestCase

from corehq.apps.es import CaseSearchES
from corehq.apps.integration.kyc.models import KycVerificationStatus
from corehq.apps.integration.payments.tables import PaymentsVerifyTable


class TestVerifySelectKycGating(SimpleTestCase):

    def _render(self, kyc_status, **overrides):
        record_data = {
            field: 'x' for field in PaymentsVerifyTable.base_columns
            if field not in PaymentsVerifyTable.OPTIONAL_FIELDS
        }
        record_data.update(user_or_case_id='b1', **overrides)
        table = PaymentsVerifyTable(data=CaseSearchES())
        table.context = {
            'user_or_cases_verification_statuses': {'b1': kyc_status} if kyc_status else {},
        }
        return table.render_verify_select(SimpleNamespace(record=record_data), 'case-1')

    def test_passed_kyc_is_selectable(self):
        assert 'disabled' not in self._render(KycVerificationStatus.PASSED)

    def test_non_passed_kyc_is_disabled(self):
        for status in [
            KycVerificationStatus.FAILED,
            KycVerificationStatus.PENDING,
            KycVerificationStatus.ERROR,
            KycVerificationStatus.INVALID,
            None,  # no KYC record
        ]:
            assert 'disabled' in self._render(status), status

    def test_missing_required_field_is_disabled_even_if_kyc_passed(self):
        assert 'disabled' in self._render(KycVerificationStatus.PASSED, amount='')
