import datetime
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

import pytz

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import user_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.filters import OR, term
from corehq.apps.es.tests.utils import es_test
from corehq.apps.export.filters import (
    NOT,
    FormSubmittedByFilter,
    GroupFormSubmittedByFilter,
    OwnerFilter,
    UserTypeFilter,
)
from corehq.apps.export.forms import (
    CaseExportFilterBuilder,
    CreateExportTagForm,
    DashboardFeedFilterForm,
    EmwfFilterFormExport,
    ExpandedMobileWorkerFilter,
    FilterCaseESExportDownloadForm,
    FormExportFilterBuilder,
)
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import LocationType
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.users.models import CommCareUser
from corehq.util.es.testing import sync_users_to_es


class FakeDomainObject(object):

    def __init__(self, uses_locations, name, date_created=None):
        self.uses_locations = uses_locations
        self.name = name
        self.date_created = date_created

    def has_privilege(self, _priv):
        return True


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
            'date_range': 'range',
            'start_date': '1992-01-30',
            'end_date': '2016-10-01',
        }
        form = DashboardFeedFilterForm(FakeDomainObject([], 'my-domain'), data=data)
        self.assertTrue(form.is_valid())

    def test_missing_fields(self):
        data = {
            'date_range': 'range',
            'start_date': '1992-01-30',
        }
        form = DashboardFeedFilterForm(FakeDomainObject([], 'my-domain'), data=data)
        self.assertFalse(form.is_valid())

    def test_bad_dates(self):
        data = {
            'date_range': 'range',
            'start_date': '1992-01-30',
            'end_date': 'banana',
        }
        form = DashboardFeedFilterForm(FakeDomainObject([], 'my-domain'), data=data)
        self.assertFalse(form.is_valid())


class TestEmwfFilterFormExport(TestCase):
    form = EmwfFilterFormExport
    filter = form.dynamic_filter_class

    def setUp(self):
        self.domain = Domain(name="testapp", is_active=True)
        self.project = FakeDomainObject(False, "foo", datetime.datetime(2015, 1, 1))
        self.subject = self.form

    def test_attributes(self):
        self.export_filter = self.subject(self.domain, pytz.utc)

        self.assertEqual(self.subject.export_user_filter, FormSubmittedByFilter)
        self.assertEqual(self.subject.dynamic_filter_class, ExpandedMobileWorkerFilter)


class TestEmwfFilterExportMixin(TestCase):
    form = EmwfFilterFormExport
    filter_builder = FormExportFilterBuilder

    @classmethod
    def setUpClass(cls):
        super(TestEmwfFilterExportMixin, cls).setUpClass()
        cls.subject = cls.form
        cls.domain = Domain(name="testapp", is_active=True)
        cls.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        cls.user_ids_slug = ['u__' + user_id for user_id in cls.user_ids]
        cls.location_ids = ['e80c5e54ab552245457d2546d0cdbb05', 'e80c5e54ab552245457d2546d0cdbb06']
        cls.location_ids_slug = ['l__' + location_id for location_id in cls.location_ids]

    def test_get_user_ids(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.assertEqual(self.filter_export._get_user_ids(self.user_ids_slug), self.user_ids)

    def test_get_users_filter(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        user_ids = self.filter_export._get_user_ids(self.user_ids_slug)
        user_filter = self.filter_builder(None, None)._get_users_filter(user_ids)

        self.assertIsInstance(user_filter, self.subject.export_user_filter)
        self.assertEqual(user_filter.submitted_by, self.user_ids)
        expected_filter = {
            'terms': {'form.meta.userID': self.user_ids}
        }
        self.assertEqual(user_filter.to_es_filter(), expected_filter)

    def test_get_location_ids(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.assertEqual(self.filter_export._get_locations_ids(self.location_ids_slug), self.location_ids)

    @patch('corehq.apps.export.forms.user_ids_at_locations_and_descendants')
    def test_get_locations_filter(self, users_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        users_patch.return_value = self.user_ids
        location_ids = self.filter_export._get_locations_ids(self.location_ids_slug)
        locations_filter = self.filter_builder(None, None)._get_locations_filter(location_ids)

        self.assertIsInstance(locations_filter, self.subject.export_user_filter)
        self.assertEqual(locations_filter.submitted_by, self.user_ids)
        expected_filter = {
            'terms': {'form.meta.userID': self.user_ids}
        }
        self.assertEqual(locations_filter.to_es_filter(), expected_filter)

    def test_get_group_ids(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        group_ids_slug = ['g__' + group_id for group_id in group_ids]

        self.assertEqual(self.filter_export._get_group_ids(group_ids_slug), group_ids)

    def test_get_selected_es_user_types(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.assertEqual(self.filter_export._get_selected_es_user_types(['t__0', 't__1']), [0, 1])


class TestEmwfFilterFormExportFilters(TestCase):
    form = EmwfFilterFormExport
    filter_builder = FormExportFilterBuilder

    @classmethod
    def setUpClass(cls):
        super(TestEmwfFilterFormExportFilters, cls).setUpClass()
        cls.subject = cls.form
        cls.domain = Domain(name="testapp", is_active=True)

    def test_attributes(self):
        export_filter = self.subject(self.domain, pytz.utc)

        self.assertEqual(export_filter.export_user_filter, FormSubmittedByFilter)
        self.assertEqual(export_filter.dynamic_filter_class, ExpandedMobileWorkerFilter)

    @patch('corehq.apps.export.filters.get_groups_user_ids')
    def test_get_group_filter(self, patch_object):
        self.filter_export = self.subject(self.domain, pytz.utc)
        group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        group_ids_slug = ['g__' + group_id for group_id in group_ids]
        patch_object.return_value = group_ids
        extracted_group_ids = self.filter_export._get_group_ids(group_ids_slug)
        group_filter = self.filter_builder(None, None)._get_group_filter(extracted_group_ids)

        self.assertIsInstance(group_filter, GroupFormSubmittedByFilter)
        self.assertEqual(group_filter.group_ids, group_ids)
        expected_filter = {
            'terms': {'form.meta.userID': group_ids}
        }
        self.assertEqual(group_filter.to_es_filter(), expected_filter)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.ACTIVE, HQUserType.DEACTIVATED])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_mobile_active_and_deactivated(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False,
                                                     active=True, deactivated=True, web=False)
        self.assertIsInstance(user_filters[0], UserTypeFilter)
        self.assertEqual(user_filters[0].user_types, self.subject._USER_MOBILE)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.ACTIVE])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_active_mobile(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False,
                                                     active=True, deactivated=False, web=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.DEACTIVATED])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_deactivated_mobile(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False,
                                                     active=False, deactivated=True, web=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.ACTIVE, HQUserType.DEACTIVATED])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_active_and_deactivated_mobile(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False,
                                                     active=True, deactivated=True, web=False)
        self.assertIsInstance(user_filters[0], UserTypeFilter)
        self.assertEqual(user_filters[0].user_types, self.subject._USER_MOBILE)

    @patch.object(form, '_get_selected_es_user_types', return_value=[HQUserType.ACTIVE, HQUserType.DEACTIVATED,
                                                                     HQUserType.ADMIN])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_admin_and_deactivated_and_active_mobile(self, fetch_user_ids_patch,
                                                                              *patches):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=True, demo=False, unknown=False, commtrack=False,
                                                     active=True, deactivated=True, web=False)

        self.assertIsInstance(user_filters[0], UserTypeFilter)
        self.assertEqual(user_filters[0].user_types, self.subject._USER_MOBILE)

        self.assertIsInstance(user_filters[1], FormSubmittedByFilter)
        self.assertEqual(user_filters[1].submitted_by, self.user_ids)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.ADMIN])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_admin(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=True, demo=False, unknown=False, commtrack=False,
                                                     active=False, deactivated=False, web=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)
        self.assertEqual(user_filters[0].submitted_by, self.user_ids)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.UNKNOWN])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_unknown(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=True, commtrack=False,
                                                     active=False, deactivated=False, web=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)
        self.assertEqual(user_filters[0].submitted_by, self.user_ids)

    @patch.object(form, '_get_selected_es_user_types', lambda x, y: [HQUserType.WEB])
    @patch.object(filter_builder, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_web(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        es_user_types = self.filter_export._get_selected_es_user_types('')
        user_filters = self.filter_builder(None, None)._get_user_type_filters(es_user_types)
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False,
                                                     active=False, deactivated=False, web=True)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)
        self.assertEqual(user_filters[0].submitted_by, self.user_ids)


@patch.object(FormExportFilterBuilder, '_get_datespan_filter', lambda self, x: None)
@patch.object(FormExportFilterBuilder, '_get_group_filter')
@patch.object(FormExportFilterBuilder, '_get_user_type_filters')
@patch.object(FormExportFilterBuilder, '_get_users_filter')
@patch.object(FormExportFilterBuilder, '_get_locations_filter')
class TestEmwfFilterFormExportFormFilters(TestCase):
    form = EmwfFilterFormExport

    @classmethod
    def setUpClass(cls):
        super(TestEmwfFilterFormExportFormFilters, cls).setUpClass()
        cls.subject = cls.form

    def test_get_model_filter_for_all_locations_access(self, locations_patch, users_patch, user_type_patch,
                                                      group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']

        data = {'date_range': '1992-01-30 to 2016-11-28'}
        export_filter_form = self.subject(domain, pytz.utc, data=data)
        self.assertTrue(export_filter_form.is_valid())
        filters = export_filter_form.get_model_filter(group_ids_slug, True, None)
        extracted_group_ids = export_filter_form._get_group_ids(group_ids_slug)

        self.assertEqual(len(filters), 1)
        group_patch.assert_called_once_with(extracted_group_ids)
        user_type_patch.assert_called_once_with([])
        users_patch.assert_called_once_with([])
        locations_patch.assert_called_once_with([])

    @patch("corehq.apps.export.forms.mobile_user_ids_at_locations")
    def test_get_model_filter_for_restricted_locations_access(self, user_ids_at_locations_patch, locations_patch,
                                                             users_patch, user_type_patch, group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        export_filter_form = self.subject(domain, pytz.utc, data=data)
        self.assertTrue(export_filter_form.is_valid())
        location_ids = ['some location', 'ids']
        filters = export_filter_form.get_model_filter(group_ids_slug, False, location_ids)
        extracted_group_ids = export_filter_form._get_group_ids(group_ids_slug)

        # There are 2 filters because the scope filter has been applied for the restricted user
        self.assertEqual(len(filters), 2)
        group_patch.assert_called_once_with(extracted_group_ids)
        user_type_patch.assert_called_once_with([])
        users_patch.assert_called_once_with([])
        locations_patch.assert_called_once_with([])


@patch.object(CaseExportFilterBuilder, '_get_datespan_filter', lambda self, x: [])
@patch.object(FilterCaseESExportDownloadForm, '_get_group_ids')
@patch.object(Group, 'get_static_user_ids_for_groups')
class TestFilterCaseESExportDownloadForm(TestCase):
    form = FilterCaseESExportDownloadForm
    filter_builder = CaseExportFilterBuilder
    filter = form.dynamic_filter_class

    @classmethod
    def setUpClass(cls):
        super(TestFilterCaseESExportDownloadForm, cls).setUpClass()
        cls.domain = Domain(name="testapp", is_active=True)
        cls.group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        cls.group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        cls.subject = cls.form

    def test_attributes(self, *patches):
        self.export_filter = self.subject(self.domain, pytz.utc)

        self.assertEqual(self.export_filter.export_user_filter, OwnerFilter)
        self.assertEqual(self.export_filter.dynamic_filter_class, CaseListFilter)

    @patch.object(filter, 'show_all_data', return_value=True)
    @patch.object(filter, 'show_project_data')
    @patch.object(filter_builder, '_get_filters_from_slugs')
    def test_get_model_filter_for_all_data(self, filters_from_slugs_patch, project_data_patch, *patches):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter_form = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter_form.is_valid())
        case_filters = self.export_filter_form.get_model_filter('', True, None)
        self.assertEqual(len(case_filters), 0)

    @patch.object(filter, 'show_project_data', return_value=True)
    @patch.object(filter, 'show_all_data', return_value=False)
    @patch.object(filter, 'selected_user_types', return_value=[HQUserType.ADMIN])
    @patch.object(filter_builder, '_get_filters_from_slugs')
    @patch.object(filter_builder, 'get_user_ids_for_user_types', return_value=['123'])
    def test_get_model_filter_for_project_data(self, fetch_user_ids_patch, filters_from_slugs_patch, *patches):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        case_filters = self.export_filter.get_model_filter(self.group_ids_slug, True, None)

        fetch_user_ids_patch.assert_called_once_with(admin=False, commtrack=True, demo=True, unknown=True,
                                                     web=False)
        assert not filters_from_slugs_patch.called
        self.assertIsInstance(case_filters[0], NOT)
        self.assertIsInstance(case_filters[0].operand_filter, OwnerFilter)
        self.assertEqual(case_filters[0].operand_filter.owner_id, ['123'])

    @patch.object(filter, 'show_deactivated_data', return_value=True)
    @patch.object(filter, 'show_project_data', return_value=True)
    @patch.object(filter, 'show_all_data', return_value=False)
    @patch.object(filter, 'selected_user_types', return_value=[HQUserType.ADMIN])
    @patch.object(filter_builder, '_get_filters_from_slugs')
    @patch.object(filter_builder, 'get_user_ids_for_user_types', return_value=['123'])
    def test_get_model_filter_for_project_data_with_deactivated_filter(self, fetch_user_ids_patch,
                                                                      filters_from_slugs_patch, *patches):
        # The show_deactivated_data filter should not change the results.
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        case_filters = self.export_filter.get_model_filter(self.group_ids_slug, True, None)

        fetch_user_ids_patch.assert_called_once_with(admin=False, commtrack=True, demo=True, unknown=True,
                                                     web=False)
        assert not filters_from_slugs_patch.called
        self.assertIsInstance(case_filters[0], NOT)
        self.assertIsInstance(case_filters[0].operand_filter, OwnerFilter)
        self.assertEqual(case_filters[0].operand_filter.owner_id, ['123'])

    @patch.object(filter, 'show_deactivated_data', return_value=True)
    @patch.object(filter, 'selected_user_types', return_value=[HQUserType.DEACTIVATED])
    @patch.object(filter_builder, '_get_filters_from_slugs')
    @patch.object(filter_builder, 'get_user_ids_for_user_types', return_value=['123'])
    def test_get_model_filter_for_deactivated_data(self, fetch_user_ids_patch, filters_from_slugs_patch, *patches):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        case_filters = self.export_filter.get_model_filter(self.group_ids_slug, True, None)

        fetch_user_ids_patch.assert_called_once_with(admin=True, commtrack=True, demo=True, unknown=True,
                                                     web=True, active=True, deactivated=False)
        assert not filters_from_slugs_patch.called
        self.assertIsInstance(case_filters[0], NOT)
        self.assertIsInstance(case_filters[0].operand_filter, OwnerFilter)
        self.assertEqual(case_filters[0].operand_filter.owner_id, ['123'])

    @patch.object(filter_builder, '_get_group_independent_filters', lambda x, y, z, a, b: [])
    def test_get_filters_from_slugs_for_all_locations_access(self, static_user_ids_for_group_patch,
                                                             group_ids_patch):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        group_ids_patch.return_value = self.group_ids
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        self.export_filter.get_model_filter(self.group_ids_slug, True, None)

        group_ids_patch.assert_called_once_with(self.group_ids_slug)
        static_user_ids_for_group_patch.assert_called_once_with(self.group_ids)

    @patch.object(filter_builder, '_get_group_independent_filters', lambda x, y, z, a, b: [])
    @patch("corehq.apps.export.forms.mobile_user_ids_at_locations")
    def test_get_filters_from_slugs_for_restricted_locations_access(self, user_ids_at_locations_patch,
                                                                    static_user_ids_for_group_patch,
                                                                    group_ids_patch):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        self.export_filter.get_model_filter(self.group_ids_slug, False, ["some", "location", "ids"])

        assert not static_user_ids_for_group_patch.called

    @patch.object(filter, 'selected_user_types')
    @patch.object(filter_builder, '_get_locations_filter')
    @patch.object(filter_builder, '_get_selected_locations_and_descendants_ids')
    @patch.object(filter_builder, '_get_users_filter')
    @patch.object(form, '_get_user_ids')
    def test_get_group_independent_filters_for_all_access(self, get_user_ids, get_users_filter, get_locations_ids,
                                                          get_locations_filter, selected_user_types, *patches):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())

        self.export_filter.get_model_filter(self.group_ids_slug, True, None)
        selected_user_types.assert_called_once_with(self.group_ids_slug)
        get_locations_ids.assert_called_once_with([])
        get_users_filter.assert_called_once_with(list(get_user_ids.return_value))
        get_user_ids.assert_called_once_with(self.group_ids_slug)

    @patch("corehq.apps.export.forms.mobile_user_ids_at_locations")
    @patch.object(filter, 'selected_user_types')
    @patch.object(filter_builder, '_get_locations_filter')
    @patch.object(filter_builder, '_get_selected_locations_and_descendants_ids')
    @patch.object(filter_builder, '_get_users_filter')
    @patch.object(form, '_get_user_ids')
    def test_get_group_independent_filters_for_restricted_access(self, get_user_ids, get_users_filter,
                                                                 get_locations_ids,
                                                                 get_locations_filter, get_es_user_types, *mocks):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())

        self.export_filter.get_model_filter(self.group_ids_slug, False, ['some', 'location', 'ids'])
        get_locations_ids.assert_called_once_with([])
        get_users_filter.assert_called_once_with(list(get_user_ids.return_value))
        get_user_ids.assert_called_once_with(self.group_ids_slug)

    @patch.object(filter_builder, '_get_filters_from_slugs')
    @patch.object(filter_builder, 'get_user_ids_for_user_types', return_value=['123'])
    def test_get_model_filter_for_default_data(self, fetch_user_ids_patch, filters_from_slugs_patch, *patches):
        data = {'date_range': '1992-01-30 to 2016-11-28'}
        self.export_filter = self.subject(self.domain, pytz.utc, data=data)
        self.assertTrue(self.export_filter.is_valid())
        # Default should be all data when filters are blank
        case_filters = self.export_filter.get_model_filter('', True, None)

        assert not fetch_user_ids_patch.called
        assert not filters_from_slugs_patch.called
        self.assertEqual(case_filters, [])


@es_test(requires=[user_adapter], setup_class=True)
class TestFormExportFilterBuilder(TestCase):
    @classmethod
    @patch('corehq.apps.users.tasks.remove_users_test_cases')
    def setUpClass(cls, _):
        super().setUpClass()

        # Setup domain
        cls.domain_obj = create_domain(name='test-form-builder')
        cls.addClassCleanup(cls.domain_obj.delete)

        # Setup locations
        LocationType.objects.get_or_create(
            domain=cls.domain_obj.name,
            name='Top Level',
        )
        cls.location_a = make_loc(
            'loc_a', domain=cls.domain_obj.name, type='Top Level'
        )

        cls.location_b = make_loc(
            'loc_b', domain=cls.domain_obj.name, type='Top Level'
        )

        # Create two mobile workers in location `loc_a` and mark mobile_worker_1 as Deactivated
        cls.mobile_worker_1 = cls._setup_mobile_worker('test_1', cls.location_a, is_active=False)
        cls.mobile_worker_2 = cls._setup_mobile_worker('test_2', cls.location_a)

        # Create a mobile worker in location `loc_b`
        cls.mobile_worker_3 = cls._setup_mobile_worker('test_3', cls.location_b)

        manager.index_refresh(user_adapter.index_name)

        # Setup export builder
        cls.form_export_builder = FormExportFilterBuilder(cls.domain_obj, pytz.utc)

    def test_active_worker_without_location_restriction(self):

        filters = self.form_export_builder.get_filters(
            can_access_all_locations=True,
            accessible_location_ids=[self.location_a.location_id],
            group_ids=[],
            user_types=[HQUserType.ACTIVE],
            user_ids=[],
            location_ids=[],
            date_range=[]
        )

        # Since can_access_all_locations is True, the filter will return submissions
        # from both location_a and location_b
        expected_filters = [
            OR(
                term(
                    'form.meta.userID',
                    sorted([self.mobile_worker_2._id, self.mobile_worker_3._id]))
            ),
        ]
        self.assertEqual(self._transform_to_es_filters(filters), expected_filters)

    def test_location_restricted_active_workers(self):

        filters = self.form_export_builder.get_filters(
            can_access_all_locations=False,
            accessible_location_ids=[self.location_a.location_id],
            group_ids=[],
            user_types=[HQUserType.ACTIVE],
            user_ids=[],
            location_ids=[],
            date_range=[]
        )

        expected_filters = [
            # Filter to get all submissions by active workers
            OR(
                term(
                    'form.meta.userID',
                    sorted([self.mobile_worker_2._id, self.mobile_worker_3._id]))
            ),
            # Scoped Filter for submissions done by users in location_a
            term('form.meta.userID', [self.mobile_worker_2._id])
        ]

        self.assertEqual(self._transform_to_es_filters(filters), expected_filters)

    def test_location_restricted_deactivated_workers(self):

        filters = self.form_export_builder.get_filters(
            can_access_all_locations=False,
            accessible_location_ids=[self.location_a.location_id],
            group_ids=[],
            user_types=[HQUserType.DEACTIVATED],
            user_ids=[],
            location_ids=[],
            date_range=[]
        )

        expected_filters = [
            # Filter to get all submissions by active workers
            OR(
                term(
                    'form.meta.userID',
                    [self.mobile_worker_1._id])
            ),
            # Scoped Filter for location_a, should include inactive workers too
            term('form.meta.userID', sorted([self.mobile_worker_2._id, self.mobile_worker_1._id]))
        ]

        self.assertEqual(self._transform_to_es_filters(filters), expected_filters)

    def _transform_to_es_filters(self, filters):
        es_filters = []
        for f in filters:
            es_filter = f.to_es_filter()
            if es_filter.get('bool'):
                path = es_filter['bool']['should'][0]['terms']
                path['form.meta.userID'] = sorted(path['form.meta.userID'])
            if es_filter.get('terms'):
                es_filter['terms']['form.meta.userID'] = sorted(es_filter['terms']['form.meta.userID'])
            es_filters.append(es_filter)
        return es_filters

    @classmethod
    def _setup_mobile_worker(cls, username, location, is_active=True):
        with sync_users_to_es():
            mobile_worker = CommCareUser.create(
                cls.domain_obj.name, f'{username}@test-form-builder.commcarehq.org', 'secret', None, None,
                is_active=is_active
            )
            mobile_worker.set_location(location)
        cls.addClassCleanup(mobile_worker.delete, cls.domain_obj.name, None)
        return mobile_worker
