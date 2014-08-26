from datetime import datetime, date
from unittest import TestCase

from couchforms.models import XFormInstance
from dimagi.utils.dates import add_months

from ..constants import *
from .case_reports import Report, OPMCase, MockCaseRow


class ChildConditionMixin(object):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.child_node = 'child_1'
        self.form_prop = 'out_of_sodas'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'check_soda_level'

    def form_json(self, value):
        return {self.child_node: {self.form_prop: value}}

    def form_with_condition(self, y, m, d):
        return XFormInstance(
            form=self.form_json(self.met_value),
            received_on=datetime(y, m, d),
            xmlns=self.xmlns,
        )

    def form_without_condition(self, y, m, d):
        return XFormInstance(
            form=self.form_json(self.not_met_value),
            received_on=datetime(y, m, d),
            xmlns=self.xmlns,
        )

    def check_condition(self, forms=None, child_age=None):
        child_age = child_age or 5
        report_year, report_month = 2014, 6
        dod_year, dod_month = add_months(report_year, report_month, -child_age)
        report = Report(
            month=report_month,
            year=report_year,
            block=getattr(self, 'block', 'Atri'),
        )
        case = OPMCase(
            forms=forms or [],
            dod=date(dod_year, dod_month, 10),
        )
        row = MockCaseRow(case, report, child_index=self.child_index)
        self.assertEqual(row.child_age, child_age)
        return getattr(row, self.row_property)

    def assertCondition(self, desired, forms=None, child_age=None):
        val = self.check_condition(forms, child_age)
        msg = "{} returned {} not {}".format(self.row_property, val, desired)
        self.assertEqual(desired, val, msg)

    @property
    def child_index(self):
        return getattr(self, '_child_index', 1)

    def test_multiple_children(self):
        self.child_node = self.child_node.replace('1', '2')
        self.form_prop = self.form_prop.replace('1', '2')
        self._child_index = 2
        self.test_condition_met()



class TestChildGrowthMonitored(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.child_node = 'child_1'
        self.form_prop = 'child1_child_growthmon'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'child_growth_calculated'

    def test_condition_met(self):
        self.assertCondition(True,
            forms=[
                self.form_without_condition(2014, 4, 15),
                self.form_with_condition(2014, 5, 15),
                self.form_without_condition(2014, 6, 15),
            ],
            child_age=6,
        )

    def test_condition_not_met(self):
        self.assertCondition(False,
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
        self.child_node = 'child_1'
        self.form_prop = 'child1_child_excbreastfed'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'child_breastfed'

    def test_missed_a_month(self):
        self.assertCondition(False,
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_without_condition(2014, 4, 15),
                self.form_with_condition(2014, 5, 15),
            ],
            child_age=6,
        )

    def test_condition_met(self):
        self.assertCondition(True,
            forms=[
                self.form_with_condition(2014, 2, 15),
                self.form_with_condition(2014, 3, 15),
                self.form_with_condition(2014, 5, 15),
                self.form_with_condition(2014, 6, 15),
                self.form_without_condition(2014, 7, 15),
            ],
            child_age=6,
        )

    def test_no_forms_returns_false(self):
        self.assertCondition(False,
            forms=[],
            child_age=6,
        )

class TestChildReceivedORS(ChildConditionMixin, TestCase):
    def setUp(self):
        self.xmlns = CFU2_XMLNS
        self.child_node = 'child_1'
        self.form_prop = 'child1_child_orszntreat'
        self.met_value = '1'
        self.not_met_value = '0'
        self.row_property = 'child_received_ors'

    def test_irrelevant_month(self):
        self.assertCondition(None, child_age=4)

    def test_child_never_sick(self):
        self.assertCondition(True,
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
        self.assertCondition(False,
            forms=[
                self.form_with_condition(2014, 3, 1),
                self.form_without_condition(2014, 4, 1),
                self.form_with_condition(2014, 5, 1),
                self.form_with_condition(2014, 6, 1),
            ],
            child_age=9,
        )

    def test_condition_met(self):
        self.assertCondition(True,
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
        self.assertCondition(None,
            forms=[
                self.form_without_condition(2014, 4, 30),
                self.form_without_condition(2014, 5, 1),
                self.form_with_condition(2014, 6, 1),
            ],
            child_age=7,
        )
