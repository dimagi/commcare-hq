from datetime import datetime, date
from unittest import TestCase

from jsonobject import (JsonObject, DictProperty, DateTimeProperty,
    StringProperty, IntegerProperty, BooleanProperty)

from casexml.apps.case.models import CommCareCase
from dimagi.utils.dates import DateSpan

from ..beneficiary import OPMCaseRow


class Report(JsonObject):
    month = IntegerProperty(required=True)
    year = IntegerProperty(required=True)
    block = StringProperty(required=True)

    @property
    def datespan(self):
        return DateSpan.from_month(self.month, self.year, inclusive=True)


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
    def __init__(self, case, report, vhnd_available=True):
        self.case = case
        self.report = report
        self.report.snapshot = None
        self.report.is_rendered_as_email = None
        self._vhnd_available = vhnd_available
        super(MockCaseRow, self).__init__(case, report)

    @property
    def vhnd_available(self):
        return self._vhnd_available


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
