from datetime import datetime, date
from unittest import TestCase

from ..constants import *
from .case_reports import Report, OPMCase, MockCaseRow
from couchforms.models import XFormInstance


class TestBirthSpacing(TestCase):
    def pregnant_form(self, y, m, d):
        return XFormInstance(
            form={'birth_spacing_prompt': '1'},
            received_on=datetime(y, m, d),
            xmlns=CFU3_XMLNS,
        )

    def not_pregnant_form(self, y, m, d):
        return XFormInstance(
            form={'birth_spacing_prompt': '2'},
            received_on=datetime(y, m, d),
            xmlns=CFU3_XMLNS,
        )

    def test_not_enough_time(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 1, 10),
        )
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 6)
        self.assertEqual(None, row.birth_spacing_years)

    def test_two_years(self):
        case = OPMCase(
            forms=[
                self.not_pregnant_form(2012, 8, 12),
                self.not_pregnant_form(2012, 10, 12),
                self.not_pregnant_form(2013, 10, 12),
            ],
            dod=date(2012, 2, 10),
        )
        report = Report(month=1, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 24)
        self.assertEqual(row.birth_spacing_years, 2)

    def test_pregnant_n_a(self):
        case = OPMCase(
            forms=[
                self.not_pregnant_form(2012, 8, 12),
                self.not_pregnant_form(2013, 3, 12),
                self.pregnant_form(2013, 10, 12),
            ],
            dod=date(2012, 4, 10),
        )
        report = Report(month=1, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 22)
        self.assertEqual(None, row.birth_spacing_years)

    def test_pregnant_two_years(self):
        case = OPMCase(
            forms=[
                self.not_pregnant_form(2012, 8, 12),
                self.not_pregnant_form(2012, 10, 12),
                self.not_pregnant_form(2013, 1, 12),
                self.pregnant_form(2013, 10, 12),
            ],
            dod=date(2012, 2, 10),
        )
        report = Report(month=1, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 24)
        self.assertFalse(row.birth_spacing_years)
