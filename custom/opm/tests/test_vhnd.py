from datetime import date, datetime, timedelta
from couchforms.models import XFormInstance
from ..constants import CFU2_XMLNS, CHILDREN_FORMS, BIRTH_PREP_XMLNS, CFU1_XMLNS
from .case_reports import OPMCaseReportTestBase, OPMCase, MockCaseRow, \
    get_relative_edd_from_preg_month, MockDataProvider
from .test_multiple_children import make_child2_form


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
            form = _child_form_with_vhnd_attendance(self.report_datetime, xmlns)
            case = OPMCase(
                forms=[form],
                dod=date(2014, 3, 10),
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, row.child_attended_vhnd)

    def test_multiple_children(self):
        for xmlns in CHILDREN_FORMS:
            form = make_child2_form(_child_form_with_vhnd_attendance(self.report_datetime, xmlns))
            case = OPMCase(
                forms=[form],
                dod=date(2014, 3, 10),
                child_index=2,
            )
            row = MockCaseRow(case, self.report, child_index=2)
            self.assertEqual(True, row.child_attended_vhnd)

    def test_outside_window(self):
        for received_on in (self.report_datetime - timedelta(days=32),
                            self.report_datetime + timedelta(days=32)):
            for xmlns in CHILDREN_FORMS:
                form = _child_form_with_vhnd_attendance(received_on, xmlns)
                case = OPMCase(
                    forms=[form],
                    dod=date(2014, 3, 10),
                )
                row = MockCaseRow(case, self.report)
                self.assertEqual(False, row.child_attended_vhnd)

    def test_multiple_forms_in_window(self):
        form1 = _child_form_with_vhnd_attendance(self.report_datetime)
        form2 = _child_form_without_vhnd_attendance(self.report_datetime + timedelta(days=1))
        case = OPMCase(
            forms=[form1, form2],
            dod=date(2014, 3, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.child_attended_vhnd)

    def test_always_positive_in_first_month(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 5, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.child_attended_vhnd)

    def test_positive_when_no_vhnd(self):
        case = OPMCase(
            forms=[],
            dod=date(2014, 3, 10),
        )
        data_provider = MockDataProvider()
        row = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertEqual(True, row.child_attended_vhnd)


class TestPregnancyVHNDNew(OPMCaseReportTestBase):

    def test_no_data_not_match(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 10),
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, row.preg_attended_vhnd)

    def test_positive_match_in_all_windows(self):
        for month in range(4, 9):
            edd = get_relative_edd_from_preg_month(self.report_date, month)
            case = OPMCase(
                forms=[_preg_form_with_vhnd_attendance(self.report_datetime)],
                edd=edd,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, row.preg_attended_vhnd)

    def test_negative_match_in_all_windows(self):
        for month in range(4, 8):
            edd = get_relative_edd_from_preg_month(self.report_date, month)
            case = OPMCase(
                forms=[_preg_form_without_vhnd_attendance(self.report_datetime)],
                edd=edd,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(False, row.preg_attended_vhnd)

    def test_always_valid_in_ninth_month(self):
        edd = get_relative_edd_from_preg_month(self.report_date, 9)
        case = OPMCase(
            forms=[],
            edd=edd,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.preg_attended_vhnd)

    def test_positive_when_no_vhnd(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 11, 10),
        )
        data_provider = MockDataProvider()
        row = MockCaseRow(case, self.report, data_provider=data_provider)
        self.assertEqual(True, row.preg_attended_vhnd)

    def test_first_window_looks_back(self):
        form = _preg_form_with_vhnd_attendance(datetime(2014, 5, 25))
        edd = get_relative_edd_from_preg_month(self.report_date, 4)
        case = OPMCase(
            forms=[form],
            edd=edd,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(True, row.preg_attended_vhnd)

class TestPregnancyVHNDLegacy(OPMCaseReportTestBase):
    # mapping month of pregnancy to case properties that trigger vhnd attendance
    month_to_property_map = (
        (4, 'attendance_vhnd_1'),
        (5, 'attendance_vhnd_2'),
        (6, 'attendance_vhnd_3'),
        (7, 'month_7_attended'),
        (8, 'month_8_attended'),
    )

    def test_positive_match_in_all_windows(self):
        for month, case_prop in self.month_to_property_map:
            edd = get_relative_edd_from_preg_month(self.report_date, month)
            case = OPMCase(
                forms=[],
                edd=edd,
                **{case_prop: '1'}
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, row.preg_attended_vhnd)

    def test_negative_match_in_all_windows(self):
        for valid_month, case_prop in self.month_to_property_map:
            for test_month in range(4, 9):
                if test_month != valid_month:
                    edd = get_relative_edd_from_preg_month(self.report_date, test_month)
                    case = OPMCase(
                        forms=[],
                        edd=edd,
                        **{case_prop: '1'}
                    )
                    row = MockCaseRow(case, self.report)
                    self.assertEqual(False, row.preg_attended_vhnd)


def _child_form_with_vhnd_attendance(received_on, xmlns=CFU1_XMLNS):
    return XFormInstance(
        received_on=received_on,
        xmlns=xmlns,
        form={
            'child_1': {
                'child1_attendance_vhnd': '1'
            }
        }
    )

def _child_form_without_vhnd_attendance(received_on, xmlns=CFU1_XMLNS):
    return XFormInstance(
        received_on=received_on,
        xmlns=xmlns,
        form={
            'child_1': {
                'child1_attendance_vhnd': '0'
            }
        },
    )

def _preg_form_with_vhnd_attendance(received_on):
    return XFormInstance(
        received_on=received_on,
        xmlns=BIRTH_PREP_XMLNS,
        form={
            'pregnancy_questions': {
                'attendance_vhnd': '1'
            }
        }
    )

def _preg_form_without_vhnd_attendance(received_on):
    return XFormInstance(
        received_on=received_on,
        xmlns=BIRTH_PREP_XMLNS,
        form={
            'pregnancy_questions': {
                'attendance_vhnd': '0'
            }
        },
    )
