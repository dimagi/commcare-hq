from datetime import date, datetime, timedelta
from couchforms.models import XFormInstance
from dimagi.utils.dates import add_months_to_date
from ..constants import *
from .case_reports import *


class TestConsistency(OPMCaseReportTestBase):
    report_year= 2014
    report_month = 6
    child_age = 6
    owner_id = 'mock_owner_id'

    def child_followup_form(self, form_props):
        return XFormInstance(
            form={},
            received_on=datetime(self.report_year, self.report_month, 9),
            xmlns=CFU1_XMLNS,
        )

    def setup_case_row(self, forms=None, services_map=None):
        """
        services_map should map prop name to a set of dates available
        """
        dod_year, dod_month = add_months(self.report_year,
                                         self.report_month,
                                         -self.child_age)
        report = Report(
            month=self.report_month,
            year=self.report_year,
            block='Atri',
        )
        case = OPMCase(
            forms=forms or [],
            dod=date(dod_year, dod_month, 10),
            owner_id=self.owner_id,
        )
        data_provider = MockDataProvider(explicit_map={
            self.owner_id: services_map or {}
        })
        row = MockCaseRow(case, report, data_provider=data_provider)
        self.assertEqual(row.child_age, self.child_age)
        return row

    def assertConsistent(self, row):
        self.assertEqual(row.total_cash, row.cash_amt)
        if not row.all_conditions_met:
            self.assertEqual(0, row.month_amt)
            self.assertEqual(0, row.bp1_cash)
            self.assertEqual(0, row.bp2_cash)
            self.assertEqual(0, row.child_cash)

    def test_same_cash(self):
        row = self.setup_case_row()
        self.assertConsistent(row)

    def test_child_met_all_conditions(self):
        forms = [
            self.child_followup_form({}),
        ]
        services_map={
            'vhnd_available': {add_months_to_date(self.report_date, -1)}
        }
        row = self.setup_case_row(forms=forms)
        self.assertTrue(row.vhnd_available)
        self.assertTrue(row.child_attended_vhnd)
