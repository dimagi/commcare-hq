from datetime import datetime, date
from unittest import TestCase

from couchforms.models import XFormInstance
from dimagi.utils.dates import add_months

from ..constants import *
from .case_reports import Report, OPMCase, MockCaseRow


class ChildConditionMixin(object):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.form_prop = 'out_of_sodas'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'check_soda_level'

    def form_with_condition(self, y, m, d):
        return XFormInstance(
            form={self.form_prop: self.met_value},
            received_on=datetime(y, m, d),
            xmlns=self.xmlns,
        )

    def form_without_condition(self, y, m, d):
        return XFormInstance(
            form={self.form_prop: self.not_met_value},
            received_on=datetime(y, m, d),
            xmlns=self.xmlns,
        )

    def check_condition(self, forms=None, child_age=None):
        child_age = child_age or 5
        report_year, report_month = 2014, 6
        dod_year, dod_month = add_months(report_year, report_month, -child_age)
        report = Report(month=report_month, year=report_year, block="Atri")
        case = OPMCase(
            forms=forms or [],
            dod=date(dod_year, dod_month, 10),
        )
        row = MockCaseRow(case, report, child_index=self.child_index)
        self.assertEqual(row.child_age, child_age)
        return getattr(row, self.row_property)

    def assertMeetsCondition(self, forms=None, child_age=None):
        msg = "{} did not return True".format(self.row_property)
        self.assertTrue(self.check_condition(forms, child_age), msg)

    def assertFailsCondition(self, forms=None, child_age=None):
        msg = "{} did not return False".format(self.row_property)
        self.assertEqual(False, self.check_condition(forms, child_age), msg)

    def assertConditionIrrelevant(self, forms=None, child_age=None):
        msg = "{} did not return None".format(self.row_property)
        self.assertEqual(None, self.check_condition(forms, child_age), msg)

    @property
    def child_index(self):
        return getattr(self, '_child_index', 1)

    def test_multiple_children(self):
        self.form_prop = self.form_prop.replace('1', '2')
        self._child_index = 2
        self.test_condition_met()



class TestChildGrowthMonitored(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.form_prop = 'child1_growthmon_calc'
        self.met_value = 'received'
        self.not_met_value = 'not_taken'
        self.row_property = 'child_growth_calculated'

    def test_condition_met(self):
        self.assertMeetsCondition(
            forms=[
                self.form_without_condition(2014, 4, 15),
                self.form_with_condition(2014, 5, 15),
                self.form_without_condition(2014, 6, 15),
            ],
            child_age=6,
        )

    def test_condition_not_met(self):
        self.assertFailsCondition(
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_without_condition(2014, 5, 15),
                self.form_with_condition(2014, 7, 15),
            ],
            child_age=6,
        )


class TestChildExclusivelyBreastfed(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU1_XMLNS
        self.form_prop = 'child1_child_excbreastfed'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'child_breastfed'

    def test_missed_a_month(self):
        self.assertFailsCondition(
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_without_condition(2014, 4, 15),
                self.form_with_condition(2014, 5, 15),
            ],
            child_age=6,
        )

    def test_condition_met(self):
        self.assertMeetsCondition(
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_with_condition(2014, 3, 15),
                self.form_with_condition(2014, 5, 15),
                self.form_with_condition(2014, 6, 15),
                self.form_without_condition(2014, 7, 15),
            ],
            child_age=6,
        )


class TestChildReceivedORS(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.form_prop = 'child1_child_orszntreat'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'child_received_ors'

    def test_irrelevant_month(self):
        self.assertConditionIrrelevant(child_age=4)

    def test_child_never_sick(self):
        self.assertMeetsCondition(
            forms=[
                XFormInstance(
                    received_on=datetime(2014, 5, 2),
                    xmlns=self.xmlns,
                ),
                XFormInstance(
                    received_on=datetime(2014, 6, 12),
                    xmlns=self.xmlns,
                ),
            ],
            child_age=9,
        )

    def test_missed_one_treatment(self):
        self.assertFailsCondition(
            forms=[
                self.form_with_condition(2014, 3, 1),
                self.form_without_condition(2014, 4, 1),
                self.form_with_condition(2014, 5, 1),
                self.form_with_condition(2014, 6, 1),
            ],
            child_age=9,
        )

    def test_condition_met(self):
        self.assertMeetsCondition(
            forms=[
                self.form_without_condition(2014, 3, 31),
                self.form_with_condition(2014, 4, 1),
                self.form_with_condition(2014, 5, 11),
                self.form_with_condition(2014, 6, 1),
                self.form_without_condition(2014, 7, 1),
            ],
            child_age=9,
        )

    def test_failure_irrelevant_month(self):
        self.assertConditionIrrelevant(
            forms=[
                self.form_without_condition(2014, 4, 30),
                self.form_without_condition(2014, 5, 1),
                self.form_with_condition(2014, 6, 1),
            ],
            child_age=7,
        )
