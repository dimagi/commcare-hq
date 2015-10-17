from unittest import TestCase
from datetime import date, datetime
from couchforms.models import XFormInstance
from ..constants import InvalidRow
from .case_reports import (OPMCaseReportTestBase, OPMCase, MockCaseRow, Report,
               offset_date, MockDataProvider)


class TestPregnancyWindowAndMonths(OPMCaseReportTestBase):

    def _offset_date(self, offset):
        """
        For a given offset, return a date that many months offset from the report date
        """
        return offset_date(self.report_date, offset)

    def test_valid_month_not_yet_delivered(self):
        # maps number of months in the future your due date is to month of pregnancy
        month_mapping = {
            0: 9,
            1: 8,
            2: 7,
            3: 6,
            4: 5,
            5: 4,
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
            edd=self._offset_date(6),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)

    def test_not_yet_in_range_by_a_lot(self):
        # 12 or more months in the future you also don't count
        case = OPMCase(
            forms=[],
            edd=self._offset_date(12),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)

    def test_past_range(self):
        # anytime after the period you don't count
        case = OPMCase(
            forms=[],
            edd=self._offset_date(-1),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)


    def test_child_first_month_not_valid(self):
        case = OPMCase(
            forms=[],
            dod=self.report_date,
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)


    def test_valid_child_month(self):
        for i in range(1, 18):
            case = OPMCase(
                forms=[],
                dod=self._offset_date(-i),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual('mother', row.status)
            self.assertEqual(i, row.child_age)

    def test_child_outside_window(self):
        case = OPMCase(
            forms=[],
            dod=self._offset_date(-50),
        )
        mock_case = MockCaseRow(case, self.report)
        self.assertTrue(mock_case.case_is_out_of_range)



class TestPregnancyFirstMonthWindow(OPMCaseReportTestBase):

    def test_first_of_month_counts(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 1),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(4, row.preg_month)

    def test_last_of_month_counts(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 30),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(4, row.preg_month)

    def test_vhnd_after_checkpoint_pregnancy(self):
        # when a VHND occurs before the window checkpoint the pregnant mother still counts for that period
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 15),
        )
        data_provider = MockDataProvider(default_date=date(2014, 6, 25))
        row = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertEqual(4, row.preg_month)

    def test_vhnd_before_checkpoint_pregnancy(self):
        # when a VHND occurs before the window checkpoint the pregnant mother
        # doesn't count for that period
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 15),
        )
        data_provider = MockDataProvider(default_date=date(2014, 6, 5))
        mock_case = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertTrue(mock_case.case_is_out_of_range)

        # the next month should actually start window 4
        row = MockCaseRow(case, Report(month=7, year=2014, block="Atri"), data_provider=data_provider)
        self.assertEqual(4, row.preg_month)
        # and so on
        row = MockCaseRow(case, Report(month=9, year=2014, block="Atri"), data_provider=data_provider)
        self.assertEqual(6, row.preg_month)


class TestChildFirstMonthWindow(OPMCaseReportTestBase):

    def test_first_of_month_counts(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 5, 1),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(1, row.child_age)

    def test_last_of_month_counts(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 5, 31),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(1, row.child_age)

    def test_vhnd_after_checkpoint_child(self):
        # when a VHND occurs after the window checkpoint the child still counts
        case = OPMCase(
            forms=[],
            dod=date(2014, 5, 15),
        )
        data_provider = MockDataProvider(default_date=date(2014, 6, 25))
        row = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertEqual(1, row.child_age)

    def test_vhnd_before_checkpoint_pregnancy(self):
        # when a VHND occurs before the window checkpoint the child doesn't count
        case = OPMCase(
            forms=[],
            dod=date(2014, 5, 15),
        )
        data_provider = MockDataProvider(default_date=date(2014, 6, 5))
        mock_case = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertTrue(mock_case.case_is_out_of_range)

        # the next month should actually start window 1
        row = MockCaseRow(case, Report(month=7, year=2014, block="Atri"), data_provider=data_provider)
        self.assertEqual(1, row.child_age)
        # and so on
        row = MockCaseRow(case, Report(month=9, year=2014, block="Atri"), data_provider=data_provider)
        self.assertEqual(3, row.child_age)


class TestFormFiltering(TestCase):
    def check_form(self, received=None, months_before=None, months_after=None, xmlns=None):
        form = XFormInstance(received_on=received or datetime(2014, 6, 15),
                    form={'foo': 'bar'},
                    xmlns=xmlns or 'moodys://falafel.palace')
        case = OPMCase([form], dod=date(2014, 1, 10))
        row = MockCaseRow(case, Report(month=6, year=2014, block="Atri"))
        return len(row.filtered_forms(xmlns, months_before, months_after)) == 1

    def assertInRange(self, y, m, d, months_before=None, months_after=None):
        self.assertTrue(self.check_form(datetime(y, m, d, 10), months_before, months_after))

    def assertNotInRange(self, y, m, d, months_before=None, months_after=None):
        self.assertFalse(self.check_form(datetime(y, m, d, 10), months_before, months_after))

    def test_forms_in_range(self):
        self.assertInRange(2014, 6, 15, 1)
        self.assertInRange(2014, 3, 15, 5)

    def test_form_higher(self):
        self.assertNotInRange(2014, 7, 15, 3)

    def test_form_lower(self):
        self.assertNotInRange(2014, 3, 15, 3)

    def test_xmlns_list(self):
        self.assertTrue(self.check_form(xmlns='alligator'))

    def test_last_day(self):
        self.assertInRange(2014, 6, 30)

    def test_one_day_late(self):
        self.assertNotInRange(2014, 7, 1)

    def test_first_day(self):
        self.assertInRange(2014, 6, 1, months_before=1)
        self.assertInRange(2014, 4, 1, months_before=3)

    def test_one_day_early(self):
        self.assertNotInRange(2014, 5, 31, months_before=1)
        self.assertNotInRange(2014, 3, 31, months_before=3)

    def test_months_after(self):
        self.assertInRange(2014, 7, 4, months_after=1)

    def test_months_after_doesnt_affect_before(self):
        self.assertNotInRange(2014, 5, 4, months_before=1, months_after=1)
