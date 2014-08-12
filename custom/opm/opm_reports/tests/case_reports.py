from datetime import datetime, date
from unittest import TestCase

from jsonobject import (JsonObject, DictProperty, DateTimeProperty,
    StringProperty, IntegerProperty, BooleanProperty, DateProperty)

from casexml.apps.case.models import CommCareCase
from dimagi.utils.dates import DateSpan
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
    opened_on = DateTimeProperty(datetime(2010, 01, 01))
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
    forms = None

    def __init__(self, case, report):
        self.case = case
        self.report = report
        self.report.snapshot = None
        self.report.is_rendered_as_email = None
        super(MockCaseRow, self).__init__(case, report)


class TestCaseReports(TestCase):
    def test_mock_data(self):
        report = Report(month=06, year=2014, block="Atri")
        form = Form(form={'foo': 'bar'}, received_on=datetime(2014, 06, 15))
        case = OPMCase(
            forms=[form],
            # add/override any desired case properties here
            edd=date(2014, 12, 10),
        )
        row = MockCaseRow(case, report)
