from datetime import date, time, datetime
from unittest import TestCase

from .case_reports import Report, OPMCase, MockCaseRow, OPMCaseReportTestBase
from couchforms.models import XFormInstance
from custom.opm.opm_reports.constants import BIRTH_PREP_XMLNS
from dimagi.utils.dates import add_months_to_date


class TestMotherWeightMonitored(TestCase):
    def setUp(self):
        self.case = OPMCase(
            forms=[],
            edd=date(2014, 9, 15),
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
    valid_edd = date(2014, 9, 15)

    def case(self, met=True):
        return OPMCase(
            forms=[],
            edd=self.valid_edd,
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

    def test_soft_block_not_checked(self):
        report = Report(month=6, year=2014, block="Wazirganj")
        row = MockCaseRow(self.case(met=False), report)
        self.assertEqual(None, row.preg_received_ifa)

    def test_legacy_never_received_ifa(self):
        row = MockCaseRow(self.case(met=False), self.report)
        self.assertEqual(False, row.preg_received_ifa)

    def test_legacy_received_ifa(self):
        row = MockCaseRow(self.case(met=True), self.report)
        self.assertTrue(row.preg_received_ifa)

    def test_received_ifa_in_forms(self):
        form = _form_with_ifa(self.report_datetime)
        case = OPMCase(
            forms=[form],
            edd=self.valid_edd,
        )
        row = MockCaseRow(case, self.report)
        self.assertTrue(row.preg_received_ifa)

    def test_received_ifa_look_back(self):
        form = _form_with_ifa(datetime.combine(add_months_to_date(self.valid_edd, -6), time()))
        case = OPMCase(
            forms=[form],
            edd=self.valid_edd,
        )
        row = MockCaseRow(case, self.report)
        self.assertTrue(row.preg_received_ifa)

    def test_received_ifa_look_back_only_6_months(self):
        form = _form_with_ifa(datetime.combine(add_months_to_date(self.valid_edd, -7), time()))
        case = OPMCase(
            forms=[form],
            edd=self.valid_edd,
        )
        row = MockCaseRow(case, self.report)
        self.assertFalse(row.preg_received_ifa)


def _form_with_ifa(received_on):
    return XFormInstance(
        received_on=received_on,
        xmlns=BIRTH_PREP_XMLNS,
        form={
            'pregnancy_questions': {
                'ifa_receive': '1'
            }
        }
    )
