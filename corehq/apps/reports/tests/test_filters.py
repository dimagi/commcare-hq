from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase, TestCase
from mock import patch
from django.test.client import RequestFactory

from corehq.apps.locations.models import LocationType
from corehq.apps.reports.filters.controllers import paginate_options
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.forms import FormsByApplicationFilterParams, FormsByApplicationFilter, \
    PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE, PARAM_SLUG_APP_ID, PARAM_SLUG_MODULE
from corehq.apps.reports.tests.test_analytics import SetupSimpleAppMixin
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.locations.tests.util import make_loc
from six.moves import range
from six.moves import map


class TestEmwfPagination(SimpleTestCase):

    def make_data_source(self, options):
        def matching_objects(query):
            if not query:
                return options
            return [o for o in options if query.lower() in o.lower()]

        def get_size(query):
            return len(matching_objects(query))

        def get_objects(query, start, size):
            return matching_objects(query)[start:start+size]

        return (get_size, get_objects)

    @property
    def data_sources(self):
        return [
            self.make_data_source(["Iron Maiden", "Van Halen", "Queen"]),
            self.make_data_source(["Oslo", "Baldwin", "Perth", "Quito"]),
            self.make_data_source([]),
            self.make_data_source(["Jdoe", "Rumpelstiltskin"]),
        ]

    def test_first_page(self):
        count, options = paginate_options(self.data_sources, "", 0, 5)
        self.assertEqual(count, 9)
        self.assertEqual(
            options,
            ["Iron Maiden", "Van Halen", "Queen", "Oslo", "Baldwin"],
        )

    def test_second_page(self):
        count, options = paginate_options(self.data_sources, "", 5, 10)
        self.assertEqual(count, 9)
        self.assertEqual(
            options,
            ["Perth", "Quito", "Jdoe", "Rumpelstiltskin"],
        )

    def test_query_first_page(self):
        query = "o"
        count, options = paginate_options(self.data_sources, query, 0, 5)
        self.assertEqual(count, 4)
        self.assertEqual(options, ["Iron Maiden", "Oslo", "Quito", "Jdoe"])

    def test_query_no_matches(self):
        query = "Waldo"
        count, options = paginate_options(self.data_sources, query, 0, 5)
        self.assertEqual(count, 0)
        self.assertEqual(options, [])


class FormsByApplicationFilterDbTest(SetupSimpleAppMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(FormsByApplicationFilterDbTest, cls).setUpClass()
        cls.class_setup()

    @classmethod
    def tearDownClass(cls):
        super(FormsByApplicationFilterDbTest, cls).tearDownClass()
        cls.app.delete()
        cls.deleted_app.delete()

    def test_get_filtered_data_by_app_id_missing(self):
        params = FormsByApplicationFilterParams([
            _make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            _make_filter(PARAM_SLUG_APP_ID, 'missing')
        ])
        results = FormsByApplicationFilter.get_filtered_data_for_parsed_params(self.domain, params)
        self.assertEqual(0, len(results))

    def test_get_filtered_data_by_app_id(self):
        params = FormsByApplicationFilterParams([
            _make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            _make_filter(PARAM_SLUG_APP_ID, self.app.id)
        ])
        results = FormsByApplicationFilter.get_filtered_data_for_parsed_params(self.domain, params)
        self.assertEqual(2, len(results))
        for i, details in enumerate(results):
            self._assert_form_details_match(i, details)

    def test_get_filtered_data_by_module_id_missing(self):
        params = FormsByApplicationFilterParams([
            _make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
            _make_filter(PARAM_SLUG_APP_ID, self.app.id),
            _make_filter(PARAM_SLUG_MODULE, '3'),
        ])
        results = FormsByApplicationFilter.get_filtered_data_for_parsed_params(self.domain, params)
        self.assertEqual(0, len(results))

    def test_get_filtered_data_by_module_id(self):
        for i in range(2):
            params = FormsByApplicationFilterParams([
                _make_filter(PARAM_SLUG_STATUS, PARAM_VALUE_STATUS_ACTIVE),
                _make_filter(PARAM_SLUG_APP_ID, self.app.id),
                _make_filter(PARAM_SLUG_MODULE, str(i)),
            ])
            results = FormsByApplicationFilter.get_filtered_data_for_parsed_params(self.domain, params)
            self.assertEqual(1, len(results))
            details = results[0]
            self._assert_form_details_match(i, details)


class TestExpandedMobileWorkerFilter(TestCase):
    def setUp(self):
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
        ]
        self.request = RequestFactory()
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_get_assigned_locations_default(self, assigned_locations_patch):
        assigned_locations_patch.return_value = self.user_assigned_locations
        emwf = ExpandedMobileWorkerFilter(self.request)
        loc_defaults = emwf._get_assigned_locations_default()
        self.assertEqual(loc_defaults, list(map(emwf.utils.location_tuple, self.user_assigned_locations)))


class TestLocationRestrictedMobileWorkerFilter(TestCase):
    def setUp(self):
        self.subject = ExpandedMobileWorkerFilter
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
        ]
        self.request = RequestFactory()
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_default_selections_for_full_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = True
        self.request.project = self.domain
        emwf = ExpandedMobileWorkerFilter(self.request)
        emwf.get_default_selections()
        assert not assigned_locations_patch.called

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_default_selections_for_restricted_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = False
        self.request.project = self.domain
        emwf = ExpandedMobileWorkerFilter(self.request)
        emwf.get_default_selections()
        assert assigned_locations_patch.called


class TestCaseListFilter(TestCase):
    def setUp(self):
        self.subject = CaseListFilter
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
        ]
        self.request = RequestFactory()
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_default_selections_for_full_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = True
        self.request.project = self.domain
        emwf = self.subject(self.request)
        default_selections = emwf.get_default_selections()
        self.assertEqual(default_selections, emwf.default_selections)
        assert not assigned_locations_patch.called

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_default_selections_for_restricted_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = False
        self.request.project = self.domain
        emwf = self.subject(self.request)
        emwf.get_default_selections()
        assert assigned_locations_patch.called


def _make_filter(slug, value):
    return {'slug': slug, 'value': value}
