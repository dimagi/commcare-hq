from ..constants import *
from .case_reports import *


class TestConsistency(OPMCaseReportTestBase):
    def assertConsistent(self, row):
        self.assertEqual(row.total_cash, row.cash_amt)
        if not row.all_conditions_met:
            self.assertEqual(0, row.month_amt)
            self.assertEqual(0, row.bp1_cash)
            self.assertEqual(0, row.bp2_cash)
            self.assertEqual(0, row.child_cash)

    def test_same_cash(self):
        row = make_case_row()
        self.assertConsistent(row)

    def test_child_met_all_conditions(self):
        row = make_case_row(
            form_props=['child1_attendance_vhnd',
                        'child1_child_register',
                        'child1_child_excbreastfed'],
            vhnd_props=['vhnd_available'],
        )
        self.assertTrue(row.vhnd_available)
        self.assertTrue(row.child_attended_vhnd)
        self.assertTrue(row.all_conditions_met)
        self.assertTrue(row.child_followup)
        self.assertConsistent(row)

    def test_skipped_vhnd(self):
        row = make_case_row(
            form_props=['child1_child_register',
                        'child1_child_excbreastfed'],
            vhnd_props=['vhnd_available'],
        )
        self.assertFalse(row.child_attended_vhnd)
        self.assertFalse(row.all_conditions_met)
        self.assertFalse(row.child_followup)
        self.assertConsistent(row)

    def test_wazirganj_block(self):
        row = make_case_row(
            form_props=[
                'child1_attendance_vhnd',
                'child1_child_register',
                'child1_child_excbreastfed'
                # 'child1_child_weight'  # This should be only for Atri block
            ],
            vhnd_props=['vhnd_available'],
            child_age=3,
            block="Wazirganj",
        )
        self.assertConsistent(row)
