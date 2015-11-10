from datetime import date
from ..constants import InvalidRow
from .case_reports import OPMCaseReportTestBase, OPMCase, MockCaseRow


class TestPregnancyStatus(OPMCaseReportTestBase):

    def test_not_yet_delivered(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual('pregnant', row.status)

    def test_delivered_before_period(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 3, 10),
            dod=date(2014, 3, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual('mother', row.status)

    def test_delivered_after_period(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 9, 10),
            dod=date(2014, 9, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual('pregnant', row.status)

    def test_no_valid_status(self):
        case = OPMCase(
            forms=[],
        )
        self.assertRaises(InvalidRow, MockCaseRow, case, self.report)

    def test_due_before_period_not_delivered(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 3, 10),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)

    def test_due_in_period_not_delivered(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 6, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual('pregnant', row.status)

    def test_due_after_period_not_delivered(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 5, 10),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)

