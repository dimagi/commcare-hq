from datetime import datetime, date, timedelta
from unittest import TestCase

from jsonobject import (JsonObject, DictProperty, DateTimeProperty,
    StringProperty, IntegerProperty, BooleanProperty, DateProperty)

from casexml.apps.case.models import CommCareCase
from dimagi.utils.dates import DateSpan, add_months
from dimagi.utils.decorators.memoized import memoized

from ..constants import *
from ..beneficiary import OPMCaseRow


class Report(JsonObject):
    month = IntegerProperty(required=True)
    year = IntegerProperty(required=True)
    block = StringProperty(required=True)

    @property
    @memoized
    def datespan(self):
        return DateSpan.from_month(self.month, self.year)


class Form(JsonObject):
    xmlns = StringProperty('something')
    form = DictProperty(required=True)
    received_on = DateTimeProperty(required=True)


class OPMCase(CommCareCase):
    opened_on = DateTimeProperty(datetime(2010, 1, 1))
    block_name = StringProperty("Sahora")
    type = StringProperty("pregnancy")
    closed = BooleanProperty(default=False)
    closed_on = DateTimeProperty()
    awc_name = StringProperty("Atri")
    owner_id = StringProperty("Sahora")

    def __init__(self, forms=None, **kwargs):
        super(OPMCase, self).__init__(**kwargs)
        self._fake_forms = forms if forms is not None else []

    def get_forms(self):
        return self._fake_forms


class MockCaseRow(OPMCaseRow):
    """
    Spoof the following fields to create example cases
    """
    def __init__(self, case, report, vhnd_availability=True):
        self.case = case
        self.report = report
        self.report.snapshot = None
        self.report.is_rendered_as_email = None
        self._vhnd_availability = vhnd_availability
        super(MockCaseRow, self).__init__(case, report)

    @property
    def vhnd_availability(self):
        return self._vhnd_availability


class OPMCaseReportTestBase(TestCase):

    def setUp(self):
        self.report_date = date(2014, 6, 1)
        self.report_datetime = datetime(2014, 6, 1)
        self.report = Report(month=6, year=2014, block="Atri")


class MockDataTest(OPMCaseReportTestBase):

    def test_mock_data(self):
        report = Report(month=6, year=2014, block="Atri")
        form = Form(form={'foo': 'bar'}, received_on=datetime(2014, 6, 15))
        case = OPMCase(
            forms=[form],
            # add/override any desired case properties here
            edd=date(2014, 12, 10),
        )
        row = MockCaseRow(case, report)


class TestMotherWeightMonitored(TestCase):
    def setUp(self):
        self.case = OPMCase(
            forms=[],
            edd=date(2014, 10, 15),
            weight_tri_1="received",
            weight_tri_2="not_taken",
       )

    def test_inapplicable_month(self):
        report = Report(month=7, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 7)
        self.assertEqual(None, row.preg_weighed)

    def test_condition_met(self):
        report = Report(month=6, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 6)
        self.assertEqual(True, row.preg_weighed)

    def test_condition_not_met(self):
        report = Report(month=9, year=2014, block="Atri")
        row = MockCaseRow(self.case, report)
        self.assertEqual(row.preg_month, 9)
        self.assertEqual(False, row.preg_weighed)


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
        self.assertEqual(True, row.child_growth_calculated)

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
        self.assertEqual(False, row.child_growth_calculated)
