from collections import defaultdict
from datetime import date, datetime, timedelta, time
from couchforms.models import XFormInstance
from ..constants import InvalidRow, CFU1_XMLNS
from .case_reports import OPMCaseReportTestBase, OPMCase, MockCaseRow, \
    offset_date, MockDataProvider
from dimagi.utils.dates import add_months_to_date
from .test_multiple_children import make_child2_form


class ConditionFourTestMixin(object):
    """
    Shared test class for two conditions that have significant overlap
    """
    expected_window = None

    @property
    def valid_dod(self):
        return offset_date(self.report_date, -self.expected_window)

    def valid_form(self, received_on):
        return self.valid_form_function(received_on)

    def get_condition(self, row):
        return self.condition_getter(row)

    def test_not_in_window(self):
        for dod in (self.valid_dod - timedelta(days=1), self.valid_dod + timedelta(days=32)):
            case = OPMCase(
                forms=[],
                dod=dod,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(None, row.child_received_measles_vaccine)

    def test_in_window_no_data(self):
        case = OPMCase(
            forms=[],
            dod=self.valid_dod
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, self.get_condition(row))

    def test_in_window_with_data(self):
        for month in range(self.expected_window - 2, self.expected_window + 1):
            form_date = datetime.combine(offset_date(self.valid_dod, month), time())
            case = OPMCase(
                forms=[self.valid_form(form_date)],
                dod=self.valid_dod,
            )
            row = MockCaseRow(case, self.report)
            self.assertEqual(True, self.get_condition(row))

    def test_one_month_extension_not_valid(self):
        form_date = offset_date(self.report_datetime, 1)
        case = OPMCase(
            forms=[self.valid_form(form_date)],
            dod=self.valid_dod,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, self.get_condition(row))

    def test_before_window_not_valid(self):
        form_date = datetime.combine(offset_date(self.valid_dod, 9), time())
        case = OPMCase(
            forms=[self.valid_form(form_date)],
            dod=self.valid_dod,
        )
        row = MockCaseRow(case, self.report)
        self.assertEqual(False, self.get_condition(row))

    def test_multiple_children(self):
        for month in range(self.expected_window - 2, self.expected_window + 1):
            form_date = datetime.combine(offset_date(self.valid_dod, month), time())
            case = OPMCase(
                forms=[make_child2_form(self.valid_form(form_date))],
                dod=self.valid_dod,
                child_index=2,
            )
            row = MockCaseRow(case, self.report, child_index=2)
            self.assertEqual(True, self.get_condition(row))


class ServiceAvailabilityTestMixIn(object):

    service_key = None
    mismatched_service_key = 'aint_no_service_with_this_name'

    def test_service_unavailable_at_all(self):
        data_provider = MockDataProvider()
        case = OPMCase(
            forms=[],
            dod=self.valid_dod,
        )
        row = MockCaseRow(case, self.report, data_provider)
        self.assertEqual(True, self.get_condition(row))

    def test_service_unavailable_partial(self):
        date = add_months_to_date(self.report_date, -2)
        data_provider = MockDataProvider(explicit_map=self._service_map(date,
                                                                        [self.service_key]))
        case = OPMCase(
            forms=[],
            dod=self.valid_dod,
            owner_id='mock_owner_id',
        )
        row = MockCaseRow(case, self.report, data_provider)
        self.assertEqual(False, self.get_condition(row))

    def test_service_unavailable_out_of_range(self):
        date = add_months_to_date(self.report_date, -3)
        data_provider = MockDataProvider(explicit_map=self._service_map(date,
                                                                        [self.service_key]))
        case = OPMCase(
            forms=[],
            dod=self.valid_dod,
            owner_id='mock_owner_id',
        )
        row = MockCaseRow(case, self.report, data_provider)
        self.assertEqual(True, self.get_condition(row))

    def test_service_unavailable_different_condition(self):
        date = add_months_to_date(self.report_date, -2)
        data_provider = MockDataProvider(explicit_map=self._service_map(date, [self.mismatched_service_key]))
        case = OPMCase(
            forms=[],
            dod=self.valid_dod,
            owner_id='mock_owner_id',
        )
        row = MockCaseRow(case, self.report, data_provider)
        self.assertEqual(True, self.get_condition(row))

    def _service_map(self, date, keys):
        inner = defaultdict(lambda: set())
        for key in keys:
            inner[key] = {date}

        return {
            'mock_owner_id': inner
        }



class TestChildMeasles(OPMCaseReportTestBase, ConditionFourTestMixin, ServiceAvailabilityTestMixIn):
    expected_window = 12
    service_key = 'stock_measlesvacc'

    def setUp(self):
        super(TestChildMeasles, self).setUp()
        self.valid_form_function = _valid_measles_form
        self.condition_getter = lambda row: row.child_received_measles_vaccine


class TestChildBirthRegistration(OPMCaseReportTestBase, ConditionFourTestMixin):
    expected_window = 6
    service_key = 'vhnd_available'

    def setUp(self):
        super(TestChildBirthRegistration, self).setUp()
        self.valid_form_function = _valid_birth_registration_form
        self.condition_getter = lambda row: row.child_birth_registered


class TestChildWeighedOnce(OPMCaseReportTestBase, ConditionFourTestMixin):
    expected_window = 3

    def setUp(self):
        super(TestChildWeighedOnce, self).setUp()
        self.valid_form_function = _valid_child_weight_registration_form
        self.condition_getter = lambda row: row.child_weighed_once


def _valid_measles_form(received_on):
    return XFormInstance(
        form={
            'child_1': {
                'child1_child_measlesvacc': '1',
            }
        },
        received_on=received_on,
        xmlns=CFU1_XMLNS,
    )


def _valid_birth_registration_form(received_on):
    return XFormInstance(
        form={
            'child_1': {
                'child1_child_register': '1',
            }
        },
        received_on=received_on,
        xmlns=CFU1_XMLNS,
    )


def _valid_child_weight_registration_form(received_on):
    return XFormInstance(
        form={
            'child_1': {
                'child1_child_weight': '1',
            }
        },
        received_on=received_on,
        xmlns=CFU1_XMLNS,
    )
