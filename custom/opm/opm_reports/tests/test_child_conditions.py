from datetime import datetime, date
from unittest import TestCase

from ..constants import *
from .case_reports import Report, Form, OPMCase, MockCaseRow


class TestChildGrowthMonitored(TestCase):
    def form_with_condition(self, y, m, d):
        return Form(
            form={'child1_growthmon_calc': 'received'},
            received_on=datetime(y, m, d),
            xmlns=CFU2_XMLNS,
        )

    def form_without_condition(self, y, m, d):
        return Form(
            form={'child1_growthmon_calc': 'not_taken'},
            received_on=datetime(y, m, d),
            xmlns=CFU2_XMLNS,
        )

    def test_condition_met(self):
        case = OPMCase(
            forms=[
                self.form_without_condition(2014, 4, 15),
                self.form_with_condition(2014, 5, 15),
                self.form_without_condition(2014, 6, 15),
            ],
            dod=date(2014, 1, 10),
        )
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 6)
        self.assertTrue(row.child_growth_calculated)

    def test_condition_not_met(self):
        case = OPMCase(
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_without_condition(2014, 5, 15),
                self.form_with_condition(2014, 7, 15),
            ],
            dod=date(2014, 1, 10),
        )
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 6)
        self.assertFalse(row.child_growth_calculated)


class TestChildExclusivelyBreastfed(TestCase):
    def breastfed_form(self, y, m, d):
        return Form(
            form={'child1_child_excbreastfed': '1'},
            received_on=datetime(y, m, d),
            xmlns=CFU1_XMLNS,
        )

    def not_breastfed_form(self, y, m, d):
        return Form(
            form={'child1_child_excbreastfed': '0'},
            received_on=datetime(y, m, d),
            xmlns=CFU1_XMLNS,
        )

    def test_missed_a_month(self):
        case = OPMCase(
            forms=[
                self.breastfed_form(2014, 2, 15),
                self.not_breastfed_form(2014, 4, 15),
                self.breastfed_form(2014, 5, 15),
            ],
            dod=date(2014, 1, 10),
        )
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 6)
        self.assertFalse(row.child_breastfed)

    def test_condition_met(self):
        case = OPMCase(
            forms=[
                self.breastfed_form(2014, 2, 15),
                self.breastfed_form(2014, 3, 15),
                self.breastfed_form(2014, 5, 15),
                self.breastfed_form(2014, 6, 15),
                self.not_breastfed_form(2014, 7, 15),
            ],
            dod=date(2014, 1, 10),
        )
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 6)
        self.assertTrue(row.child_breastfed)
