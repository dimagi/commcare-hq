from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import clear_domain_names
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.models import LocationType
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
from corehq.apps.reports.tests.test_analytics import SetupSimpleAppMixin
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DomainMembership,
    WebUser,
)


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


@es_test(requires=[user_adapter])
class TestEMWFilterOutput(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'emwf-filter-output-test'
        cls.user = WebUser(username='test@cchq.com', domains=[cls.domain])
        cls.user.domain_memberships = [DomainMembership(domain=cls.domain, role_id='MYROLE')]
        from corehq.apps.reports.tests.filters.user_list import dummy_user_list

        for user in dummy_user_list:
            user_obj = CouchUser.get_by_username(user['username'])
            if user_obj:
                user_obj.delete('')
        cls.user_list = []
        for user in dummy_user_list:
            user_obj = CommCareUser.create(**user) if user['doc_type'] == 'CommcareUser'\
                else WebUser.create(**user)
            user_obj.save()
            cls.user_list.append(user_obj)

    def setUp(self):
        super().setUp()
        self._send_users_to_es()

    @classmethod
    def tearDownClass(cls):
        for user in cls.user_list:
            user.delete(cls.domain, deleted_by=None)
        super().tearDownClass()

    def _send_users_to_es(self):
        for user_obj in self.user_list:
            user_adapter.index(
                user_obj,
                refresh=True
            )

    def test_with_active_slug(self):
        mobile_user_and_group_slugs = ['t__0']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['active1', 'active2']
        self.assertCountEqual(user_ids, expected_ids)

    def test_with_deactivated_slug(self):
        mobile_user_and_group_slugs = ['t__5']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['deactive2', 'deactive1']
        self.assertCountEqual(user_ids, expected_ids)

    def test_with_webuser_slug(self):
        mobile_user_and_group_slugs = ['t__6']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['web1']
        self.assertCountEqual(user_ids, expected_ids)

    def test_with_active_type_and_inactive_user_slug(self):
        mobile_user_and_group_slugs = ['t__0', 'u__deactive1']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['active1', 'active2', 'deactive1']
        self.assertCountEqual(user_ids, expected_ids)

    def test_with_deactivated_type_and_active_user_slug(self):
        mobile_user_and_group_slugs = ['t__5', 'u__active1']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['deactive1', 'deactive2', 'active1']
        self.assertCountEqual(user_ids, expected_ids)

    def test_with_web_type_and_active_deactivated_user_slug(self):
        mobile_user_and_group_slugs = ['t__6', 'u__active1', 'u__deactive1']
        user_query = ExpandedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
            self.user,
        )
        user_ids = user_query.values_list('_id', flat=True)
        expected_ids = ['web1', 'active1', 'deactive1']
        self.assertCountEqual(user_ids, expected_ids)
