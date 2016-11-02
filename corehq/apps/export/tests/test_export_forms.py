import datetime
from collections import namedtuple

import pytz
from django.test import SimpleTestCase
from mock import patch, MagicMock

from corehq.apps.export.filter_builders import ESFormExportFilterBuilder
from corehq.apps.export.filters import FormSubmittedByFilter
from corehq.apps.export.forms import FilterFormESExportDownloadForm, DashboardFeedFilterForm, CreateExportTagForm

DomainObject = namedtuple('DomainObject', ['uses_locations', 'name'])


class TestCreateExportTagForm(SimpleTestCase):

    def test_required_fields(self):
        # Confirm that form cannot be submitted without case_type when model_type is case
        data = {
            'model_type': 'case',
            'app_type': "application",
            'application': "fdksajhfjkqwf",
        }
        form = CreateExportTagForm(True, True, data)
        # Missing case_type
        self.assertFalse(form.is_valid())

    def test_static_model_type(self):
        # Confirm that model_type is cleaned according to export permissions
        data = {
            'model_type': 'form',  # This should be switch to case in the cleaned_data
            'app_type': 'application',
            'application': 'asdfjwkeghrk',
            "case_type": "my_case_type"
        }
        form = CreateExportTagForm(
            has_form_export_permissions=False,
            has_case_export_permissions=True,
            data=data
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['model_type'], 'case')


@patch('corehq.apps.export.forms.Group', new=MagicMock(get_reporting_groups=lambda x: []))
class TestDashboardFeedFilterForm(SimpleTestCase):

    def test_good_data(self):
        data = {
            'type_or_group': 'group',
            'date_range': 'range',
            'start_date': '1992-01-30',
            'end_date': '2016-10-01',
        }
        form = DashboardFeedFilterForm(DomainObject([], 'my domain'), data=data)
        self.assertTrue(form.is_valid())

    def test_missing_fields(self):
        data = {
            'type_or_group': 'group',
            'date_range': 'range',
            'start_date': '1992-01-30',
        }
        form = DashboardFeedFilterForm(DomainObject([], 'my domain'), data=data)
        self.assertFalse(form.is_valid())

    def test_bad_dates(self):
        data = {
            'type_or_group': 'group',
            'date_range': 'range',
            'start_date': '1992-01-30',
            'end_date': 'banana',
        }
        form = DashboardFeedFilterForm(DomainObject([], 'my domain'), data=data)
        self.assertFalse(form.is_valid())


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
@patch('corehq.apps.export.forms.Group', new=MagicMock(
    get_reporting_groups=lambda x: [MagicMock(_id='some_group_id', name='my group')]
))
class TestFilterFormESExportDownloadForm(SimpleTestCase):

    def setUp(self):
        self.project = DomainObject(False, "foo")

    def test_get_datespan_filter(self):

        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid())

        filter_builder = ESFormExportFilterBuilder(
            self.project.name, pytz.utc, 'group', [], [], form.cleaned_data['date_range']
        )

        datespan_filter = filter_builder._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_get_group_filter(self):
        # Confirm that FilterFormESExportDownloadForm._get_group_filter() returns
        # a filter with the correct group_id and correct base_filter.
        form_data = {
            'type_or_group': 'group',
            'group': 'some_group_id',
            'date_range': '2015-06-25 to 2016-02-19',
        }
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)

        self.assertTrue(form.is_valid(), "Form had the following errors: {}".format(form.errors))

        filter_builder = ESFormExportFilterBuilder(
            self.project.name,
            pytz.utc,
            form.cleaned_data['type_or_group'],
            form.cleaned_data['group'],
            form.cleaned_data['user_types'],
            form.cleaned_data['date_range']
        )

        group_filter = filter_builder._get_group_filter()
        self.assertEqual(group_filter.group_id, 'some_group_id')
        self.assertEqual(group_filter.base_filter, FormSubmittedByFilter)
