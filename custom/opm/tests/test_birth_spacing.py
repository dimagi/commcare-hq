from datetime import datetime, date
from unittest import TestCase

from ..constants import *
from .case_reports import Report, OPMCase, MockCaseRow
from .test_child_conditions import ChildConditionMixin
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
            dod=date(2013, 12, 10),
        )
        report = Report(month=6, year=2014, block="Wazirganj")
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
            dod=date(2012, 1, 10),
        )
        report = Report(month=1, year=2014, block="Wazirganj")
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
            dod=date(2012, 3, 10),
        )
        report = Report(month=1, year=2014, block="Wazirganj")
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
            dod=date(2012, 1, 10),
        )
        report = Report(month=1, year=2014, block="Wazirganj")
        row = MockCaseRow(case, report)
        self.assertEqual(row.child_age, 24)
        self.assertFalse(row.birth_spacing_years)


class TestWeightGradeNormal(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU3_XMLNS
        self.form_prop = 'interpret_grade'
        self.row_property = 'weight_grade_normal'
        self.met_value = 'normal'
        self.not_met_value = 'MAM'
        self.block = 'Atri'

    def form_json(self, value):
        return {self.form_prop: value}

    def test_wrong_block(self):
        self.block = 'wazirganj'
        self.assertCondition(
            None,
            forms=[],
            child_age=24,
        )

    def test_no_forms(self):
        self.assertCondition(False,
            forms=[],
            child_age=24,
        )

    def test_no_forms_in_window(self):
        self.assertCondition(False,
            forms=[
                self.form_without_condition(2013, 4, 12),
                self.form_with_condition(2014, 2, 12),
            ],
            child_age=24,
        )

    def test_uses_last_form(self):
        self.assertCondition(False,
            forms=[
                self.form_with_condition(2014, 5, 24),
                # it needs to find this latest form and return False
                self.form_without_condition(2014, 6, 12),
                self.form_with_condition(2014, 6, 1),
            ],
            child_age=24,
        )

    def test_condition_met(self):
        # This is for year 2, so the fn should return 2
        self.assertCondition(2,
            forms=[
                self.form_without_condition(2014, 4, 12),
                self.form_without_condition(2014, 5, 12),
                self.form_without_condition(2014, 6, 1),
                self.form_with_condition(2014, 6, 12),
            ],
            child_age=24,
        )

    def test_condition_met_year_3(self):
        # This is for year 2, so the fn should return 2
        self.assertCondition(3,
            forms=[
                self.form_without_condition(2014, 4, 12),
                self.form_without_condition(2014, 5, 12),
                self.form_without_condition(2014, 6, 1),
                self.form_with_condition(2014, 6, 12),
            ],
            child_age=36,
        )

    def test_multiple_children(self):
        self.form_prop = 'interpret_grade_2'
        self._child_index = 2
        self.test_condition_met()
