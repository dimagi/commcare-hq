from datetime import date
from unittest import TestCase

from .case_reports import Report, OPMCase, MockCaseRow, OPMCaseReportTestBase


class TestMotherWeightMonitored(TestCase):
    def setUp(self):
        self.case = OPMCase(
            forms=[],
            edd=date(2014, 10, 15),
            weight_tri_1="received",
            weight_tri_2="not_taken",
       )

    def test_inapplicable_month(self):
        report = Report(month=7, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 7)
        self.assertEqual(None, row.preg_weighed)

    def test_condition_met(self):
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 6)
        self.assertTrue(row.preg_weighed)

    def test_condition_not_met(self):
        report = Report(month=9, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 9)
        self.assertFalse(row.preg_weighed)


class TestMotherReceivedIFA(OPMCaseReportTestBase):
    def case(self, met=True):
        return OPMCase(
            forms=[],
            edd=date(2014, 10, 15),
            ifa_tri_1='received' if met else 'not_taken',
       )

    def test_irrelevant_months(self):
        for month in (4, 5, 7, 8):
            report = Report(month=month, year=2014, block="Atri")
            row = MockCaseRow(self.case(False), report)
            # with an edd in October, preg_month lines up with calendar month
            self.assertEqual(row.preg_month, month)
            self.assertEqual(None, row.preg_received_ifa)

    def test_setup(self):
        row = MockCaseRow(self.case(), self.report)
        self.assertEqual(row.preg_month, 6)

    def test_soft_block_n_a(self):
        report = Report(month=6, year=2014, block="Wazirganj")
        row = MockCaseRow(self.case(met=False), report)
        self.assertEqual(None, row.preg_received_ifa)

    def test_never_received_ifa(self):
        row = MockCaseRow(self.case(met=False), self.report)
        self.assertEqual(False, row.preg_received_ifa)

    def test_condition_met(self):
        row = MockCaseRow(self.case(met=True), self.report)
        self.assertTrue(row.preg_received_ifa)
