from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import clear_domain_names
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.controllers import paginate_options
from corehq.apps.reports.filters.forms import (
    PARAM_SLUG_APP_ID,
    PARAM_SLUG_MODULE,
    PARAM_SLUG_STATUS,
    PARAM_VALUE_STATUS_ACTIVE,
    FormsByApplicationFilter,
    FormsByApplicationFilterParams,
)
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.tests.test_analytics import SetupSimpleAppMixin
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import generate_cases, has_permissions


class TestEmwfPagination(SimpleTestCase):

    def make_data_source(self, options):
        def matching_objects(query):
            if not query:
                return options
            return [o for o in options if query.lower() in o.lower()]

        def get_size(query):
            return len(matching_objects(query))

        def get_objects(query, start, size):
            return matching_objects(query)[start:start + size]

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
        clear_domain_names('test')
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code)
        ]
        self.request = RequestFactory()
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    def tearDown(self):
        self.domain.delete()
        super().tearDown()

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_get_assigned_locations_default(self, assigned_locations_patch):
        assigned_locations_patch.return_value = self.user_assigned_locations
        emwf = ExpandedMobileWorkerFilter(self.request)
        loc_defaults = emwf._get_assigned_locations_default()
        self.assertEqual(loc_defaults, list(map(emwf.utils.location_tuple, self.user_assigned_locations)))


class TestLocationRestrictedMobileWorkerFilter(TestCase):
    def setUp(self):
        self.subject = ExpandedMobileWorkerFilter
        clear_domain_names('test')
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code)
        ]
        self.request = RequestFactory().get('/a/{self.domain}/')
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    def tearDown(self):
        self.domain.delete()
        super().tearDown()

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

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_selections_for_restricted_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = False
        self.request.project = self.domain
        emwf = ExpandedMobileWorkerFilter(self.request)
        usa = SQLLocation(
            domain=self.domain.name,
            name='The United States of America',
            site_code='usa',
            location_type=self.location_type,
            location_id='1',
        )
        usa.save()
        india = SQLLocation(
            domain=self.domain.name,
            name='India',
            site_code='in',
            location_type=self.location_type,
            location_id='2',
        )
        india.save()
        assigned_locations_patch.return_value = [usa, india]
        self.assertEqual(
            emwf.selected,
            [
                {'id': 'l__1', 'text': 'The United States of America [location]'},
                {'id': 'l__2', 'text': 'India [location]'}
            ]
        )


class TestCaseListFilter(TestCase):
    def setUp(self):
        self.subject = CaseListFilter
        clear_domain_names('test')
        self.domain = Domain(name='test', is_active=True)
        self.domain.save()
        self.location_type = LocationType.objects.create(domain=self.domain.name, name='testtype')
        self.user_assigned_locations = [
            make_loc('root', domain=self.domain.name, type=self.location_type.code)
        ]
        self.request = RequestFactory()
        self.request.couch_user = WebUser()
        self.request.domain = self.domain

    def tearDown(self):
        self.domain.delete()
        super().tearDown()

    @patch('corehq.apps.users.models.WebUser.get_sql_locations')
    def test_default_selections_for_full_access(self, assigned_locations_patch):
        self.request.can_access_all_locations = True
        self.request.project = self.domain
        emwf = self.subject(self.request)
        emwf.get_default_selections()
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


@es_test(requires=[user_adapter], setup_class=True)
class TestEMWFilterOutput(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.domain = 'emwf-filter-output-test'
        cls.domain_obj = Domain(name=cls.domain, is_active=True)
        cls.domain_obj.save()
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.location_type = LocationType.objects.create(domain=cls.domain, name='Place')
        cls.accessible_location = SQLLocation.objects.create(
            site_code='accessible place', domain=cls.domain, location_type=cls.location_type)
        cls.inaccessible_location = SQLLocation.objects.create(
            site_code='inaccessible place', domain=cls.domain, location_type=cls.location_type)

        cls.user = WebUser.create(cls.domain, 'test@cchq.com', 'password', None, None)
        cls.user.set_location(cls.domain, cls.accessible_location)

        cls.user_list = []
        for UserClass, user_id, is_active, location in [
                (CommCareUser, 'active', True, None),
                (CommCareUser, 'active_accessible', True, cls.accessible_location),
                (CommCareUser, 'active_inaccessible', True, cls.inaccessible_location),
                (CommCareUser, 'deactive', False, None),
                (CommCareUser, 'deactive_accessible', False, cls.accessible_location),
                (CommCareUser, 'deactive_inaccessible', False, cls.inaccessible_location),
                (WebUser, 'web', True, None),
                (WebUser, 'web_accessible', True, cls.accessible_location),
                (WebUser, 'web_inaccessible', True, cls.inaccessible_location),
                (WebUser, 'web_deactive', False, cls.accessible_location),
        ]:
            user_obj = UserClass.create(
                domain=cls.domain,
                uuid=user_id,
                username=user_id,
                password='Some secret Pass',
                created_by=None,
                created_via=None,
                timezone="UTC",
                is_active=is_active,
                commit=False,
            )
            if location and UserClass is CommCareUser:
                user_obj.set_location(location, commit=False)
            if location and UserClass is WebUser:
                user_obj.set_location(cls.domain, location, commit=False)
            user_obj.save(fire_signals=False)
            cls.user_list.append(user_obj)
            user_adapter.index(
                user_obj,
                refresh=True
            )
            cls.addClassCleanup(user_obj.delete, None, None)


ACTIVE = f't__{HQUserType.ACTIVE}'
DEMO_USER = f't__{HQUserType.DEMO_USER}'
ADMIN = f't__{HQUserType.ADMIN}'
UNKNOWN = f't__{HQUserType.UNKNOWN}'
COMMTRACK = f't__{HQUserType.COMMTRACK}'
DEACTIVATED = f't__{HQUserType.DEACTIVATED}'
WEB = f't__{HQUserType.WEB}'
DEACTIVATED_WEB = f't__{HQUserType.DEACTIVATED_WEB}'


@generate_cases([
    ([ACTIVE], ['active', 'active_accessible', 'active_inaccessible']),
    ([DEACTIVATED], ['deactive', 'deactive_accessible', 'deactive_inaccessible']),
    ([WEB], ['web', 'web_accessible', 'web_inaccessible']),
    ([DEACTIVATED_WEB], ['web_deactive']),
    ([ACTIVE, 'u__deactive'], ['active', 'active_accessible', 'active_inaccessible', 'deactive']),
    ([DEACTIVATED, 'u__active'], ['deactive', 'deactive_accessible', 'deactive_inaccessible', 'active']),
    ([WEB, 'u__active', 'u__deactive'], ['web', 'web_accessible', 'web_inaccessible', 'active', 'deactive']),
], TestEMWFilterOutput)
def test_user_es_query(self, slugs, expected_ids):
    user_query = ExpandedMobileWorkerFilter.user_es_query(self.domain, slugs, self.user)
    self.assertCountEqual(user_query.values_list('_id', flat=True), expected_ids)


@generate_cases([
    ([ACTIVE], ['active_accessible']),
    ([DEACTIVATED], ['deactive_accessible']),
    (['u__active_accessible'], ['active_accessible']),
    (['u__deactive_accessible'], ['deactive_accessible']),
    ([WEB], ['web', 'web_accessible', 'web_inaccessible']),  # This is definitely wrong
    # (['u__web_accessible'], ['web_accessible']),  # This fails hard
    ([ACTIVE, 'u__deactive_accessible'], ['active_accessible', 'deactive_accessible']),
], TestEMWFilterOutput)
def test_restricted_user_es_query(self, slugs, expected_ids):
    with has_permissions(access_all_locations=False):
        user_query = ExpandedMobileWorkerFilter.user_es_query(self.domain, slugs, self.user)
        self.assertCountEqual(user_query.values_list('_id', flat=True), expected_ids)


@generate_cases([
    (['u__active'],),
    # (['u__web_inaccessible'],),  # This fails hard
], TestEMWFilterOutput)
def test_restricted_user_es_query_errors(self, slugs):
    with has_permissions(access_all_locations=False):
        with self.assertRaises(PermissionDenied):
            ExpandedMobileWorkerFilter.user_es_query(self.domain, slugs, self.user)
