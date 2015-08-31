from collections import defaultdict
from datetime import datetime, date
from unittest import TestCase

from dimagi.ext.jsonobject import (JsonObject, DateTimeProperty,
    StringProperty, IntegerProperty, BooleanProperty)

from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from dimagi.utils.dates import DateSpan, add_months

from ..beneficiary import OPMCaseRow
from .. import constants
from ..reports import CaseReportMixin, SharedDataProvider


class AggressiveDefaultDict(defaultdict):
    """
    Like a normal defaultdict, except it ignores any default you pass with
    mydict.get() and always returns True to the in operator.
    """

    def __contains__(self, item):
        return True

    def get(self, key, default=None):
        return self[key]


class MockDataProvider(SharedDataProvider):
    """
    Mock data provider to manually specify vhnd availability per user
    """
    def __init__(self, default_date=None, explicit_map=None):
        super(MockDataProvider, self).__init__()

        if explicit_map is not None:
            # convert map to a defaultdict
            results = defaultdict(lambda: defaultdict(lambda: set()))
            for owner, availability in explicit_map.items():
                for prop, dates in availability.items():
                    results[owner][prop].update(dates)
            self.service_map = results

        else:
            get_default_set = lambda: {default_date} if default_date is not None else set()

            def get_date_set_dict():
                return AggressiveDefaultDict(get_default_set)

            self.service_map = AggressiveDefaultDict(get_date_set_dict)

    @property
    def _service_dates(self):
        return self.service_map

    @property
    def forms_by_case(self):
        assert getattr(self, 'cases', None) is not None, \
            "MockDataProvider was not instantiated with cases"
        return {case._id: case.get_forms() for case in self.cases}


class Report(CaseReportMixin, JsonObject):
    month = IntegerProperty(required=True)
    year = IntegerProperty(required=True)
    block = StringProperty(required=True)

    def __init__(self, *args, **kwargs):
        super(Report, self).__init__(*args, **kwargs)
        self._extra_row_objects = []

    _data_provider = None
    @property
    def data_provider(self):
        return self._data_provider

    @property
    def datespan(self):
        return DateSpan.from_month(self.month, self.year, inclusive=True)

    def set_extra_row_objects(self, row_objects):
        self._extra_row_objects = row_objects


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
        self._id = "z640804p375ps5u2yx7"
        self._fake_forms = forms if forms is not None else []

    def get_forms(self):
        return self._fake_forms

    class Meta:
        # This is necessary otherwise tests get sad
        app_label = "opm"


class MockCaseRow(OPMCaseRow):
    """
    Spoof the following fields to create example cases
    """
    def __init__(self, case, report, data_provider=None, child_index=1, **kwargs):
        self.case = case
        self.report = report
        self.report.is_rendered_as_email = None
        self.report._data_provider = data_provider or MockDataProvider(report.datespan.enddate.date())
        self.report._data_provider.cases = [case]
        super(MockCaseRow, self).__init__(case, report, child_index=child_index, **kwargs)


class OPMCaseReportTestBase(TestCase):

    def setUp(self):
        self.report_date = date(2014, 6, 1)
        self.report_datetime = datetime(2014, 6, 1)
        self.report = Report(month=6, year=2014, block="Atri")


def get_relative_edd_from_preg_month(report_date, month):
    months_until_edd = 9 - month
    new_year, new_month = add_months(report_date.year, report_date.month, months_until_edd)
    return type(report_date)(new_year, new_month, 1)


def offset_date(reference_date, offset):
    new_year, new_month = add_months(reference_date.year, reference_date.month, offset)
    return type(reference_date)(new_year, new_month, 1)


class MockDataTest(OPMCaseReportTestBase):

    def test_mock_data(self):
        report = Report(month=6, year=2014, block="Atri")
        form = XFormInstance(form={'foo': 'bar'}, received_on=datetime(2014, 6, 15))
        case = OPMCase(
            forms=[form],
            # add/override any desired case properties here
            edd=date(2014, 11, 10),
        )
        row = MockCaseRow(case, report)


def make_case_row(form_props=None, vhnd_props=None, block='Atri', child_age=6):
    """
    Accepts lists of properties available in form and at the vhnd
    and returns a corresponding case row
    """
    report_year = 2014
    report_month = 6
    date_in_month = datetime(2014, 6, 10)
    child_age = child_age
    owner_id = 'mock_owner_id'

    forms = [XFormInstance(
        form={'child_1': {prop: '1' for prop in form_props or []}},
        received_on=date_in_month,
        xmlns=constants.CFU1_XMLNS,
    )]

    dod_year, dod_month = add_months(report_year, report_month, -child_age)
    case = OPMCase(
        forms=forms or [],
        dod=date(dod_year, dod_month, 10),
        owner_id=owner_id,
    )

    data_provider = MockDataProvider(explicit_map={
        owner_id: {
            prop: {date_in_month.date()}
            for prop in vhnd_props or []
        }
    })

    report = Report(
        month=report_month,
        year=report_year,
        block=block,
    )

    row = MockCaseRow(case, report, data_provider=data_provider)
    assert row.child_age == child_age
    return row
