from datetime import datetime
from django.test import TestCase, override_settings
from ..tasks import EpisodeVoucherUpdate

from .utils import ENikshayCaseStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestVoucherCounts(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestVoucherCounts, self).setUp()
        self.cases = self.create_case_structure()

    def make_voucher(self, prescription, num_days, date):
        return self.create_voucher_case(
            prescription.case_id, {
                'final_prescription_num_days': num_days,
                'date_fulfilled': date,
            }
        )

    def test_basic_voucher_update(self):
        prescription1 = self.create_prescription_case()
        self.make_voucher(prescription1, 12, datetime(2017, 1, 1))
        self.make_voucher(prescription1, 7, datetime(2017, 1, 3))
        prescription2 = self.create_prescription_case()
        self.make_voucher(prescription2, 16, datetime(2017, 1, 2))
        self.make_voucher(prescription2, 10, datetime(2017, 1, 4))
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.episode).update_json(),
            {
                "prescription_total_days": 12 + 7 + 16 + 10,
                "prescription_total_days_threshold_30": '2017-01-03T00:00:00.000000Z',
            }
        )

    def test_thresholds(self):
        prescription = self.create_prescription_case()
        self.make_voucher(prescription, 29, datetime(2017, 1, 2))
        self.make_voucher(prescription, 1, datetime(2017, 1, 1))
        # It should hit 30 now, and should flp the order of the above two
        self.make_voucher(prescription, 7, datetime(2017, 1, 3))
        # This one should trigger both the 60 and 90 thresholds
        self.make_voucher(prescription, 70, datetime(2017, 1, 4))
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.episode).update_json(),
            {
                "prescription_total_days": 29 + 1 + 7 + 70,
                "prescription_total_days_threshold_30": '2017-01-02T00:00:00.000000Z',
                "prescription_total_days_threshold_60": '2017-01-04T00:00:00.000000Z',
                "prescription_total_days_threshold_90": '2017-01-04T00:00:00.000000Z',
            }
        )
