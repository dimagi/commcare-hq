from django.test import TestCase, override_settings
from ..tasks import EpisodeVoucherUpdate

from .utils import ENikshayCaseStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestVoucherCounts(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestVoucherCounts, self).setUp()
        self.cases = self.create_case_structure()

    def test_basic_voucher_update(self):
        def make_voucher(prescription, num_days):
            return self.create_voucher_case(
                prescription.case_id,
                {'final_prescription_num_days': num_days}
            )

        prescription1 = self.create_prescription_case()
        make_voucher(prescription1, 3)
        make_voucher(prescription1, 5)
        prescription2 = self.create_prescription_case()
        make_voucher(prescription2, 9)
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.episode).update_json(),
            {
                'prescription_total_days': 3 + 5 + 9,
            }
        )
