import datetime
from collections import namedtuple

import pytz
from django.test import SimpleTestCase, TestCase
from mock import patch

from corehq.apps.export.filters import FormSubmittedByFilter, OwnerFilter
from corehq.apps.export.forms import (
    FilterFormESExportDownloadForm,
    BaseFilterExportDownloadForm,
    EmwfFilterFormExport,
    LocationRestrictedMobileWorkerFilter,
    FilterCaseESExportDownloadForm
)
from corehq.apps.domain.models import Domain
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestFilterFormESExportDownloadForm(SimpleTestCase):

    def setUp(self):
        DomainObject = namedtuple('DomainObject', ['uses_locations', 'name'])
        self.project = DomainObject(False, "foo")

    def test_get_datespan_filter(self):
        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        datespan_filter = form._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_get_group_filter(self):
        """
        Confirm that FilterFormESExportDownloadForm._get_group_filter() returns
        a filter with the correct group_id and correct base_filter.
        """
        form_data = {
            'type_or_group': 'group',
            'group': 'some_group_id',
            'date_range': '2015-06-25 to 2016-02-19',
        }
        form = FilterFormESExportDownloadForm(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid(), "Form had the following errors: {}".format(form.errors))
        group_filter = form._get_group_filter()
        self.assertEqual(group_filter.group_id, 'some_group_id')
        self.assertEqual(group_filter.base_filter, FormSubmittedByFilter)

    def test_export_to_es_user_types_map(self):
        mapping = {'mobile': ['mobile'], 'demo_user': ['demo'], 'supply': ['supply'],
                   'unknown': ['unknown', 'system', 'web']}
        self.assertEqual(
            FilterFormESExportDownloadForm._EXPORT_TO_ES_USER_TYPES_MAP,
            mapping
        )

    def test_skip_layout_default(self):
        self.assertFalse(BaseFilterExportDownloadForm.skip_layout)


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestEmwfFilterExportMixin(TestCase):
    def setUp(self):
        self.domain = Domain(name="testapp", is_active=True)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        self.user_ids_slug = ['u__' + user_id for user_id in self.user_ids]
        self.location_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        self.location_ids_slug = ['l__' + location_id for location_id in self.location_ids]

    def test_get_user_ids(self):
        self.filter_export = EmwfFilterFormExport(self.domain, pytz.utc)

        self.assertEqual(self.filter_export._get_user_ids(self.user_ids_slug), self.user_ids)

    def test_get_users_filter(self):
        self.filter_export = EmwfFilterFormExport(self.domain, pytz.utc)
        user_filter = self.filter_export._get_users_filter(self.user_ids_slug)

        self.assertIsInstance(user_filter, FormSubmittedByFilter)
        self.assertEqual(user_filter.submitted_by, self.user_ids)
        expected_filter = {
            'terms': {'form.meta.userID': self.user_ids}
        }
        self.assertEqual(user_filter.to_es_filter(), expected_filter)

    def test_get_location_ids(self):
        self.filter_export = EmwfFilterFormExport(self.domain, pytz.utc)

        self.assertEqual(self.filter_export._get_locations_ids(self.location_ids_slug), self.location_ids)

    @patch('corehq.apps.es.users.UserES.users_at_locations_and_descendants')
    def test_get_locations_filter(self, users_patch):
        self.filter_export = EmwfFilterFormExport(self.domain, pytz.utc)
        users = [
            {'_id': 'e80c5e54ab552245457d2546d0cdbb03'},
            {'_id': 'e80c5e54ab552245457d2546d0cdbb04'}
        ]
        users_patch.return_value = users
        locations_filter = self.filter_export._get_locations_filter(self.location_ids_slug)

        self.assertIsInstance(locations_filter, FormSubmittedByFilter)
        self.assertEqual(locations_filter.submitted_by, self.user_ids)
        expected_filter = {
            'terms': {'form.meta.userID': self.user_ids}
        }
        self.assertEqual(locations_filter.to_es_filter(), expected_filter)

    def test_get_group_ids(self):
        self.filter_export = EmwfFilterFormExport(self.domain, pytz.utc)
        group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']

        self.assertEqual(self.filter_export._get_group_ids(group_ids_slug), group_ids)


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
@patch.object(EmwfFilterFormExport, '_get_datespan_filter', lambda x: None)
@patch.object(EmwfFilterFormExport, '_get_group_filter')
@patch.object(EmwfFilterFormExport, '_get_user_type_filter')
@patch.object(EmwfFilterFormExport, '_get_users_filter')
@patch.object(EmwfFilterFormExport, '_get_locations_filter')
class TestEmwfFilterFormExport(TestCase):
    def test_attributes(self, *patches):
        domain = Domain(name="testapp", is_active=True)
        export_filter = EmwfFilterFormExport(domain, pytz.utc)

        self.assertTrue(export_filter.skip_layout)
        self.assertEqual(export_filter.export_user_filter, FormSubmittedByFilter)
        self.assertEqual(export_filter.es_user_filter, LocationRestrictedMobileWorkerFilter)

    def test_get_form_filter_for_all_locations_access(self, locations_patch, users_patch, user_type_patch,
                                                      group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        EmwfFilterFormExport(domain, pytz.utc).get_form_filter(group_ids_slug, True)

        group_patch.assert_called_once_with(group_ids_slug)
        user_type_patch.assert_called_once_with(group_ids_slug)
        users_patch.assert_called_once_with(group_ids_slug)
        locations_patch.assert_called_once_with(group_ids_slug)

    def test_get_form_filter_for_restricted_locations_access(self, locations_patch, users_patch,
                                                             user_type_patch, group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        EmwfFilterFormExport(domain, pytz.utc).get_form_filter(group_ids_slug, False)

        assert not group_patch.called, 'User Filter Called for restricted location access'
        assert not user_type_patch.called, 'User Type Filter Called for restricted location access'
        users_patch.assert_called_once_with(group_ids_slug)
        locations_patch.assert_called_once_with(group_ids_slug)


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
@patch.object(FilterCaseESExportDownloadForm, '_get_datespan_filter', lambda x: [])
@patch.object(FilterCaseESExportDownloadForm, '_get_group_ids')
@patch.object(Group, 'get_static_user_ids_for_groups')
@patch.object(Group, 'get_case_sharing_groups')
@patch.object(SQLLocation, 'get_case_sharing_locations_ids')
class TestFilterCaseESExportDownloadForm(TestCase):
    def setUp(self):
        self.domain = Domain(name="testapp", is_active=True)
        self.group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        self.group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']

    @patch.object(FilterCaseESExportDownloadForm, '_get_group_independent_filters', lambda x, y, z: [])
    def test_attributes(self, *patches):
        self.export_filter = FilterCaseESExportDownloadForm(self.domain, pytz.utc)

        self.assertTrue(self.export_filter.skip_layout)
        self.assertEqual(self.export_filter.export_user_filter, OwnerFilter)
        self.assertEqual(self.export_filter.es_user_filter, CaseListFilter)

    @patch.object(FilterCaseESExportDownloadForm, '_get_group_independent_filters', lambda x, y, z: [])
    def test_get_case_filter_for_all_locations_access(self, case_sharing_locations_ids_patch,
                                                      case_sharing_groups_patch, static_user_ids_for_group_patch,
                                                      group_ids_patch):
        group_ids_patch.return_value = self.group_ids
        self.export_filter = FilterCaseESExportDownloadForm(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, True)

        group_ids_patch.assert_called_once_with(self.group_ids_slug)
        static_user_ids_for_group_patch.assert_called_once_with(self.group_ids)
        assert not case_sharing_groups_patch.called
        assert not case_sharing_locations_ids_patch.called

    @patch.object(FilterCaseESExportDownloadForm, '_get_group_independent_filters', lambda x, y, z: [])
    def test_get_case_filter_for_restricted_locations_access(self, case_sharing_locations_ids_patch,
                                                             case_sharing_groups_patch,
                                                             static_user_ids_for_group_patch, group_ids_patch):
        self.export_filter = FilterCaseESExportDownloadForm(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, False)

        assert not group_ids_patch.called
        assert not static_user_ids_for_group_patch.called
        assert not case_sharing_groups_patch.called
        case_sharing_locations_ids_patch.assert_called_once_with(self.domain.name)

    @patch.object(FilterCaseESExportDownloadForm, '_get_es_user_types')
    @patch.object(FilterCaseESExportDownloadForm, '_get_locations_filter')
    @patch.object(FilterCaseESExportDownloadForm, '_get_locations_ids')
    @patch.object(FilterCaseESExportDownloadForm, '_get_users_filter')
    def test_get_group_independent_filters_for_all_access(self, get_users_filter,
                                                          get_locations_ids, get_locations_filter,
                                                          get_es_user_types, *patches):
        self.export_filter = FilterCaseESExportDownloadForm(self.domain, pytz.utc)
        self.export_filter._get_group_independent_filters(self.group_ids_slug, True)
        get_es_user_types.assert_called_once_with(self.group_ids_slug)
        get_locations_filter.assert_called_once_with(self.group_ids_slug)
        get_locations_ids.assert_called_once_with(self.group_ids_slug)
        get_users_filter.assert_called_once_with(self.group_ids_slug)

    @patch.object(FilterCaseESExportDownloadForm, '_get_es_user_types')
    @patch.object(FilterCaseESExportDownloadForm, '_get_locations_filter')
    @patch.object(FilterCaseESExportDownloadForm, '_get_locations_ids')
    @patch.object(FilterCaseESExportDownloadForm, '_get_users_filter')
    def test_get_group_independent_filters_for_restricted_access(self, get_users_filter,
                                                                 get_locations_ids, get_locations_filter,
                                                                 get_es_user_types, *patches):
        self.export_filter = FilterCaseESExportDownloadForm(self.domain, pytz.utc)
        self.export_filter._get_group_independent_filters(self.group_ids_slug, False)
        assert not get_es_user_types.called
        get_locations_filter.assert_called_once_with(self.group_ids_slug)
        get_locations_ids.assert_called_once_with(self.group_ids_slug)
        get_users_filter.assert_called_once_with(self.group_ids_slug)
