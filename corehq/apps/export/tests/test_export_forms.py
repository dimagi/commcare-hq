import datetime
from collections import namedtuple

import pytz
from django.test import SimpleTestCase, TestCase
from mock import patch

from corehq.apps.export.filters import (
    FormSubmittedByFilter,
    OwnerFilter,
    GroupFormSubmittedByFilter,
    UserTypeFilter,
    NOT
)
from corehq.apps.export.forms import (
    BaseFilterExportDownloadForm,
    EmwfFilterFormExport,
    LocationRestrictedMobileWorkerFilter,
    FilterCaseESExportDownloadForm
)
from corehq.apps.domain.models import Domain
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.models import HQUserType


class TestBaseFilterExportDownloadForm(SimpleTestCase):
    def test_skip_layout_default(self):
        self.assertFalse(BaseFilterExportDownloadForm.skip_layout)


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestEmwfFilterFormExport(TestCase):
    form = EmwfFilterFormExport
    filter = form.dynamic_filter_class

    def setUp(self):
        DomainObject = namedtuple('DomainObject', ['uses_locations', 'name'])
        self.domain = Domain(name="testapp", is_active=True)
        self.project = DomainObject(False, "foo")
        self.subject = self.form

    def test_attributes(self):
        self.export_filter = self.subject(self.domain, pytz.utc)

        self.assertTrue(self.export_filter.skip_layout)
        self.assertEqual(self.subject.export_user_filter, FormSubmittedByFilter)
        self.assertEqual(self.subject.dynamic_filter_class, LocationRestrictedMobileWorkerFilter)

    def test_get_datespan_filter(self):
        form_data = {'date_range': '2015-06-25 to 2016-02-19'}
        form = self.subject(self.project, pytz.utc, form_data)
        self.assertTrue(form.is_valid())
        datespan_filter = form._get_datespan_filter()
        self.assertEqual(datespan_filter.lt, datetime.datetime(2016, 2, 20, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.gte, datetime.datetime(2015, 6, 25, tzinfo=pytz.utc))
        self.assertEqual(datespan_filter.lte, None)
        self.assertEqual(datespan_filter.gt, None)

    def test_export_to_es_user_types_map(self):
        mapping = {'mobile': ['mobile'], 'demo_user': ['demo'], 'supply': ['supply'],
                   'unknown': ['unknown', 'system', 'web']}
        self.assertEqual(
            self.subject._EXPORT_TO_ES_USER_TYPES_MAP,
            mapping
        )


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestEmwfFilterExportMixin(TestCase):
    form = EmwfFilterFormExport

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
        user_filter = self.filter_export._get_users_filter(self.user_ids_slug)

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
        locations_filter = self.filter_export._get_locations_filter(self.location_ids_slug)

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

    def test_get_es_user_types(self):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.assertEqual(self.filter_export._get_es_user_types(['t__0', 't__1']), [0, 1])


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
class TestEmwfFilterFormExportFilters(TestCase):
    form = EmwfFilterFormExport

    @classmethod
    def setUpClass(cls):
        super(TestEmwfFilterFormExportFilters, cls).setUpClass()
        cls.subject = cls.form
        cls.domain = Domain(name="testapp", is_active=True)

    def test_attributes(self):
        export_filter = self.subject(self.domain, pytz.utc)

        self.assertTrue(export_filter.skip_layout)
        self.assertEqual(export_filter.export_user_filter, FormSubmittedByFilter)
        self.assertEqual(export_filter.dynamic_filter_class, LocationRestrictedMobileWorkerFilter)

    @patch('corehq.apps.export.filters.get_groups_user_ids')
    def test_get_group_filter(self, patch_object):
        self.filter_export = self.subject(self.domain, pytz.utc)
        group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        group_ids_slug = ['g__' + group_id for group_id in group_ids]
        patch_object.return_value = group_ids
        group_filter = self.filter_export._get_group_filter(group_ids_slug)

        self.assertIsInstance(group_filter, GroupFormSubmittedByFilter)
        self.assertEqual(group_filter.group_ids, group_ids)
        expected_filter = {
            'terms': {'form.meta.userID': group_ids}
        }
        self.assertEqual(group_filter.to_es_filter(), expected_filter)

    @patch.object(form, '_get_es_user_types', lambda x, y: [HQUserType.REGISTERED])
    @patch.object(form, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_mobile(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        user_filters = self.filter_export._get_user_type_filter('')
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=False, commtrack=False)
        self.assertIsInstance(user_filters[0], UserTypeFilter)
        self.assertEqual(user_filters[0].user_types, self.subject._USER_MOBILE)

    @patch.object(form, '_get_es_user_types', lambda x, y: [HQUserType.ADMIN])
    @patch.object(form, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_admin(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        user_filters = self.filter_export._get_user_type_filter('')
        fetch_user_ids_patch.assert_called_once_with(admin=True, demo=False, unknown=False, commtrack=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)
        self.assertEqual(user_filters[0].submitted_by, self.user_ids)

    @patch.object(form, '_get_es_user_types', return_value=[HQUserType.REGISTERED, HQUserType.ADMIN])
    @patch.object(form, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_admin_and_mobile(self, fetch_user_ids_patch, *patches):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        user_filters = self.filter_export._get_user_type_filter('')
        fetch_user_ids_patch.assert_called_once_with(admin=True, demo=False, unknown=False, commtrack=False)

        self.assertIsInstance(user_filters[0], UserTypeFilter)
        self.assertEqual(user_filters[0].user_types, self.subject._USER_MOBILE)

        self.assertIsInstance(user_filters[1], FormSubmittedByFilter)
        self.assertEqual(user_filters[1].submitted_by, self.user_ids)

    @patch.object(form, '_get_es_user_types', lambda x, y: [HQUserType.UNKNOWN])
    @patch.object(form, 'get_user_ids_for_user_types')
    def test_get_user_type_filter_for_unknown(self, fetch_user_ids_patch):
        self.filter_export = self.subject(self.domain, pytz.utc)
        self.user_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        fetch_user_ids_patch.return_value = self.user_ids
        user_filters = self.filter_export._get_user_type_filter('')
        fetch_user_ids_patch.assert_called_once_with(admin=False, demo=False, unknown=True, commtrack=False)
        self.assertIsInstance(user_filters[0], FormSubmittedByFilter)
        self.assertEqual(user_filters[0].submitted_by, self.user_ids)


@patch('corehq.apps.reports.util.get_first_form_submission_received', lambda x: datetime.datetime(2015, 1, 1))
@patch.object(EmwfFilterFormExport, '_get_datespan_filter', lambda x: None)
@patch.object(EmwfFilterFormExport, '_get_group_filter')
@patch.object(EmwfFilterFormExport, '_get_user_type_filter')
@patch.object(EmwfFilterFormExport, '_get_users_filter')
@patch.object(EmwfFilterFormExport, '_get_locations_filter')
class TestEmwfFilterFormExportFormFilters(TestCase):
    form = EmwfFilterFormExport

    @classmethod
    def setUpClass(cls):
        super(TestEmwfFilterFormExportFormFilters, cls).setUpClass()
        cls.subject = cls.form

    def test_get_form_filter_for_all_locations_access(self, locations_patch, users_patch, user_type_patch,
                                                      group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        self.subject(domain, pytz.utc).get_form_filter(group_ids_slug, True)

        group_patch.assert_called_once_with(group_ids_slug)
        user_type_patch.assert_called_once_with(group_ids_slug)
        users_patch.assert_called_once_with(group_ids_slug)
        locations_patch.assert_called_once_with(group_ids_slug)

    def test_get_form_filter_for_restricted_locations_access(self, locations_patch, users_patch,
                                                             user_type_patch, group_patch):
        domain = Domain(name="testapp", is_active=True)
        group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        self.subject(domain, pytz.utc).get_form_filter(group_ids_slug, False)

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
    form = FilterCaseESExportDownloadForm
    filter = form.dynamic_filter_class

    @classmethod
    def setUpClass(cls):
        super(TestFilterCaseESExportDownloadForm, cls).setUpClass()
        cls.domain = Domain(name="testapp", is_active=True)
        cls.group_ids = ['e80c5e54ab552245457d2546d0cdbb03', 'e80c5e54ab552245457d2546d0cdbb04']
        cls.group_ids_slug = ['g__e80c5e54ab552245457d2546d0cdbb03', 'g__e80c5e54ab552245457d2546d0cdbb04']
        cls.subject = cls.form

    @patch.object(form, '_get_group_independent_filters', lambda x, y, z: [])
    def test_attributes(self, *patches):
        self.export_filter = self.subject(self.domain, pytz.utc)

        self.assertTrue(self.export_filter.skip_layout)
        self.assertEqual(self.export_filter.export_user_filter, OwnerFilter)
        self.assertEqual(self.export_filter.dynamic_filter_class, CaseListFilter)

    @patch.object(filter, 'show_all_data', return_value=True)
    @patch.object(filter, 'show_project_data')
    @patch.object(form, '_get_filters_from_slugs')
    def test_get_case_filter_for_all_data(self, filters_from_slugs_patch, project_data_patch, *patches):
        self.export_filter = self.subject(self.domain, pytz.utc)
        case_filters = self.export_filter.get_case_filter('', True)
        assert not project_data_patch.called
        assert not filters_from_slugs_patch.called
        self.assertEqual(len(case_filters), 0)

    @patch.object(filter, 'show_project_data', return_value=True)
    @patch.object(filter, 'show_all_data', return_value=False)
    @patch.object(filter, 'selected_user_types', return_value=[HQUserType.ADMIN])
    @patch.object(form, '_get_filters_from_slugs')
    @patch.object(form, 'get_user_ids_for_user_types', return_value=['123'])
    def test_get_case_filter_for_project_data(self, fetch_user_ids_patch, filters_from_slugs_patch, *patches):
        self.export_filter = self.subject(self.domain, pytz.utc)
        case_filters = self.export_filter.get_case_filter('', True)

        fetch_user_ids_patch.assert_called_once_with(admin=False, unknown=True, demo=True, commtrack=True)
        assert not filters_from_slugs_patch.called

        self.assertIsInstance(case_filters[0], NOT)
        self.assertIsInstance(case_filters[0].operand_filter, OwnerFilter)
        self.assertEqual(case_filters[0].operand_filter.owner_id, ['123'])

    @patch.object(form, '_get_group_independent_filters', lambda x, y, z: [])
    def test_get_filters_from_slugs_for_all_locations_access(self, case_sharing_locations_ids_patch,
                                                             case_sharing_groups_patch,
                                                             static_user_ids_for_group_patch, group_ids_patch):
        group_ids_patch.return_value = self.group_ids
        self.export_filter = self.subject(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, True)

        group_ids_patch.assert_called_once_with(self.group_ids_slug)
        static_user_ids_for_group_patch.assert_called_once_with(self.group_ids)
        assert not case_sharing_groups_patch.called
        assert not case_sharing_locations_ids_patch.called

    @patch.object(form, '_get_group_independent_filters', lambda x, y, z: [])
    def test_get_filters_from_slugs_for_restricted_locations_access(self, case_sharing_locations_ids_patch,
                                                                    case_sharing_groups_patch,
                                                                    static_user_ids_for_group_patch,
                                                                    group_ids_patch):
        self.export_filter = self.subject(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, False)

        assert not group_ids_patch.called
        assert not static_user_ids_for_group_patch.called
        assert not case_sharing_groups_patch.called
        case_sharing_locations_ids_patch.assert_called_once_with(self.domain.name)

    @patch.object(filter, 'selected_user_types')
    @patch.object(form, '_get_locations_filter')
    @patch.object(form, '_get_locations_ids')
    @patch.object(form, '_get_users_filter')
    def test_get_group_independent_filters_for_all_access(self, get_users_filter, get_locations_ids,
                                                          get_locations_filter, get_es_user_types, *patches):
        self.export_filter = self.subject(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, True)
        get_es_user_types.assert_called_once_with(self.group_ids_slug)
        get_locations_filter.assert_called_once_with(self.group_ids_slug)
        get_locations_ids.assert_called_once_with(self.group_ids_slug)
        get_users_filter.assert_called_once_with(self.group_ids_slug)

    @patch.object(filter, 'selected_user_types')
    @patch.object(form, '_get_locations_filter')
    @patch.object(form, '_get_locations_ids')
    @patch.object(form, '_get_users_filter')
    def test_get_group_independent_filters_for_restricted_access(self, get_users_filter, get_locations_ids,
                                                                 get_locations_filter, get_es_user_types, *mocks):
        self.export_filter = self.subject(self.domain, pytz.utc)
        self.export_filter.get_case_filter(self.group_ids_slug, False)
        assert not get_es_user_types.called
        get_locations_filter.assert_called_once_with(self.group_ids_slug)
        get_locations_ids.assert_called_once_with(self.group_ids_slug)
        get_users_filter.assert_called_once_with(self.group_ids_slug)
