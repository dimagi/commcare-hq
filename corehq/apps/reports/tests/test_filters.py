from unittest.mock import patch

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
from corehq.apps.users.models import (
    CommCareUser,
    DomainMembership,
    WebUser,
)
from corehq.util.test_utils import generate_cases


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
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
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
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
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
            make_loc('root', domain=self.domain.name, type=self.location_type.code).sql_location
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
    USERS = [
        (CommCareUser, 'active1', {}),
        (CommCareUser, 'active2', {}),
        (CommCareUser, 'deactive1', {'is_active': False}),
        (CommCareUser, 'deactive2', {'is_active': False}),
        (WebUser, 'web1', {}),
    ]

    @classmethod
    def setUpTestData(cls):
        cls.domain = 'emwf-filter-output-test'
        cls.user = WebUser(username='test@cchq.com', domains=[cls.domain])
        cls.user.domain_memberships = [DomainMembership(domain=cls.domain, role_id='MYROLE')]
        cls.user_list = []
        for UserClass, user_id, kwargs in cls.USERS:
            user_obj = UserClass.create(
                domain=cls.domain,
                uuid=user_id,
                username=user_id,
                password='Some secret Pass',
                created_by=None,
                created_via=None,
                timezone="UTC",
                **kwargs
            )
            user_obj.save()
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


@generate_cases([
    ([ACTIVE], ['active1', 'active2']),
    ([DEACTIVATED], ['deactive2', 'deactive1']),
    ([WEB], ['web1']),
    ([ACTIVE, 'u__deactive1'], ['active1', 'active2', 'deactive1']),
    ([DEACTIVATED, 'u__active1'], ['deactive1', 'deactive2', 'active1']),
    ([WEB, 'u__active1', 'u__deactive1'], ['web1', 'active1', 'deactive1']),
], TestEMWFilterOutput)
def test_user_es_query(self, slugs, expected_ids):
    user_query = ExpandedMobileWorkerFilter.user_es_query(self.domain, slugs, self.user)
    self.assertCountEqual(user_query.values_list('_id', flat=True), expected_ids)
