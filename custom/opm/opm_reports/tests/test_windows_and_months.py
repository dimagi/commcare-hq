from datetime import date
from custom.opm.opm_reports.constants import InvalidRow
from custom.opm.opm_reports.tests import OPMCaseReportTestBase, OPMCase, MockCaseRow
from dimagi.utils.dates import add_months


class TestPregnancyWindowAndMonths(OPMCaseReportTestBase):

    def _offset_date(self, offset):
        """
        For a given offset, return a date that many months offset from the report date
        """
        new_year, new_month = add_months(self.report_date.year, self.report_date.month, offset)
        return date(new_year, new_month, 1)

    def test_valid_window_not_yet_delivered(self):
        # maps number of months in the future your due date is to window
        window_mapping = {
            1: 2,
            2: 2,
            3: 2,
            4: 1,
            5: 1,
            6: 1,
        }
        for i, window in window_mapping.items():
            case = OPMCase(
                forms=[],
                edd=self._offset_date(i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('pregnant', row.status)
            self.assertEqual(window, row.window)

    def test_valid_month_not_yet_delivered(self):
        # maps number of months in the future your due date is to month of pregnancy
        month_mapping = {
            1: 9,
            2: 8,
            3: 7,
            4: 6,
            5: 5,
            6: 4,
        }
        for i, month in month_mapping.items():
            case = OPMCase(
                forms=[],
                edd=self._offset_date(i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('pregnant', row.status)
            self.assertEqual(month, row.preg_month)

    def test_not_yet_in_range(self):
        # 7 or more months in the future you don't count
        case = OPMCase(
            forms=[],
            edd=self._offset_date(7),
        )
        self.assertRaises(InvalidRow, MockCaseRow, case, self.report)

    def test_past_range(self):
        # anytime in the period or after you don't count
        case = OPMCase(
            forms=[],
            edd=self.report_date,
        )
        self.assertRaises(InvalidRow, MockCaseRow, case, self.report)

    def test_valid_child_window(self):
        # maps number of months in the past your delivery date was to window of child calc
        # todo: this seems really funny. Should 0-2 map to 3, 3-5 map to 4, etc.?
        window_mapping = {
            0: 1,
            1: 1,
            2: 2,
            3: 2,
            4: 2,
            5: 3,
            6: 3,
            7: 3,
            8: 4,
            9: 4,
            10: 4,
            11: 5,
            12: 5,
            13: 5,
            14: 6,
            15: 6,
            16: 6,
        }
        for i, window in window_mapping.items():
            case = OPMCase(
                forms=[],
                dod=self._offset_date(-i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('mother', row.status)
            self.assertEqual(window, row.window)

    def test_valid_child_window(self):
        # maps number of months in the past your delivery date was to window of child calc
        # todo: this seems really funny. Should 0-2 map to 3, 3-5 map to 4, etc.?
        window_mapping = {
            0: 1,
            1: 1,
            2: 1,
            3: 2,
            4: 2,
            5: 2,
            6: 3,
            7: 3,
            8: 3,
            9: 4,
            10: 4,
            11: 4,
            12: 5,
            13: 5,
            14: 5,
            15: 6,
            16: 6,
            17: 6,
        }
        for i, window in window_mapping.items():
            case = OPMCase(
                forms=[],
                dod=self._offset_date(-i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('mother', row.status)
            self.assertEqual(window, row.window, 'value {} expected window {} but was {}'.format(
                i, window, row.window
            ))


    def test_valid_child_month(self):
        for i in range(18):
            case = OPMCase(
                forms=[],
                dod=self._offset_date(-i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('mother', row.status)
            self.assertEqual(i + 1, row.child_age)