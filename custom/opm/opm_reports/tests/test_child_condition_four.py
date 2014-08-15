from datetime import date, datetime, timedelta, time
from couchforms.models import XFormInstance
from custom.opm.opm_reports.constants import InvalidRow, CFU1_XMLNS
from custom.opm.opm_reports.tests.case_reports import OPMCaseReportTestBase, OPMCase, MockCaseRow, \
    offset_date


class TestChildMeasles(OPMCaseReportTestBase):

    def test_not_in_window(self):
        for dod in (date(2014, 3, 10), date(2013, 3, 10)):
            case = OPMCase(
                forms=[],
                dod=dod,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(None, row.child_received_measles_vaccine)

    def test_in_window_no_data(self):
        case = OPMCase(
            forms=[],
            dod=offset_date(self.report_date, -11)
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, row.child_received_measles_vaccine)

    def test_in_window_with_data(self):
        dod = offset_date(self.report_date, -11)
        for month in (10, 11, 12):
            form_date = datetime.combine(offset_date(dod, month), time())
            case = OPMCase(
                forms=[_valid_form(form_date)],
                dod=dod,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, row.child_received_measles_vaccine)

    def test_one_month_extension_valid(self):
        dod = offset_date(self.report_date, -11)
        form_date = offset_date(self.report_datetime, 1)
        case = OPMCase(
            forms=[_valid_form(form_date)],
            dod=dod,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.child_received_measles_vaccine)

    def test_two_month_extension_not_valid(self):
        dod = offset_date(self.report_date, -11)
        form_date = offset_date(self.report_datetime, 2)
        case = OPMCase(
            forms=[_valid_form(form_date)],
            dod=dod,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, row.child_received_measles_vaccine)

    def test_before_window_not_valid(self):
        dod = offset_date(self.report_date, -11)
        form_date = datetime.combine(offset_date(dod, 9), time())
        case = OPMCase(
            forms=[_valid_form(form_date)],
            dod=dod,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, row.child_received_measles_vaccine)


def _valid_form(received_on):
    return XFormInstance(
        form={
            'child1': {
                'child1_child_measlesvacc': '1',
            }
        },
        received_on=received_on,
        xmlns=CFU1_XMLNS,
    )