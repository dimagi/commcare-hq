from datetime import date, datetime, timedelta
from custom.opm.opm_reports.constants import InvalidRow, CFU2_XMLNS, CHILDREN_FORMS
from custom.opm.opm_reports.tests.case_reports import OPMCaseReportTestBase, OPMCase, MockCaseRow, Form


class TestChildVHND(OPMCaseReportTestBase):

    def test_no_data_not_match(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 3, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, row.child_attended_vhnd)

    def test_single_match_in_all_forms(self):
        for xmlns in CHILDREN_FORMS:
            form = Form(
                form={'child1_vhndattend_calc': 'received'},
                received_on=self.report_datetime,
                xmlns=xmlns,
            )
            case = OPMCase(
                forms=[form],
                dod=date(2014, 3, 10),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, row.child_attended_vhnd)

    def test_outside_window(self):
        for received_on in (self.report_datetime - timedelta(days=32),
                            self.report_datetime + timedelta(days=32)):
            for xmlns in CHILDREN_FORMS:
                form = Form(
                    form={'child1_vhndattend_calc': 'received'},
                    received_on=received_on,
                    xmlns=xmlns,
                )
                case = OPMCase(
                    forms=[form],
                    dod=date(2014, 3, 10),
                )
                row = MockCaseRow(case, self.report)
                self.assertEqual(False, row.child_attended_vhnd)

    def test_multiple_forms_in_window(self):
        form1 = Form(
            form={'child1_vhndattend_calc': 'received'},
            received_on=self.report_datetime,
            xmlns=CFU2_XMLNS,
        )
        form2 = Form(
            form={'child1_vhndattend_calc': 'not_taken'},
            received_on=self.report_datetime + timedelta(days=1),
            xmlns=CFU2_XMLNS,
        )
        case = OPMCase(
            forms=[form1, form2],
            dod=date(2014, 3, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.child_attended_vhnd)
