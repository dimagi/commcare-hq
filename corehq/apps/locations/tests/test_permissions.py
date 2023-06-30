import json
import random
import string
import uuid
from unittest import mock

from django.http import HttpResponse
from django.urls import reverse

from casexml.apps.case.tests.util import delete_all_xforms

from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.views.mobile import users as user_views
from corehq.form_processor.utils.xform import (
    TestFormMetadata,
    get_simple_wrapped_form,
)
from corehq.util.test_utils import create_and_save_a_case

from ..forms import LocationFilterForm
from ..permissions import can_edit_form_location, user_can_access_case
from ..views import EditLocationView, LocationsListView
from .util import LocationHierarchyTestCase


class TestNewFormEditRestrictions(LocationHierarchyTestCase):
    domain = 'TestNewFormEditRestrictions-domain'
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Brookline', []),
            ])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        super(TestNewFormEditRestrictions, cls).setUpClass()
        cls.extra_setup()
        cls.restrict_user_to_assigned_locations(cls.middlesex_web_user)
        cls.restrict_user_to_assigned_locations(cls.massachusetts_web_user)
        cls.restrict_user_to_assigned_locations(cls.locationless_web_user)

    @classmethod
    def tearDownClass(cls):
        cls.extra_teardown()
        super(TestNewFormEditRestrictions, cls).tearDownClass()

    def test_can_edit_form_in_county(self):
        self.assertCanEdit(self.middlesex_web_user, self.cambridge_form)

    def test_cant_edit_out_of_county(self):
        self.assertCannotEdit(self.middlesex_web_user, self.boston_form)

    def test_can_edit_any_form(self):
        self.assertCanEdit(self.massachusetts_web_user, self.cambridge_form)
        self.assertCanEdit(self.massachusetts_web_user, self.boston_form)

    def test_project_admin_can_edit_anything(self):
        self.project_admin.get_domain_membership(self.domain).is_admin = True
        self.project_admin.save()

        self.assertCanEdit(self.project_admin, self.cambridge_form)
        self.assertCanEdit(self.project_admin, self.boston_form)

    def test_unassigned_web_user_cant_edit_anything(self):
        self.assertCannotEdit(self.locationless_web_user, self.cambridge_form)
        self.assertCannotEdit(self.locationless_web_user, self.boston_form)

    # The rest of this class is helper methods and setup

    @classmethod
    def make_web_user(cls, location):
        username = ''.join(random.sample(string.ascii_letters, 8))
        user = WebUser.create(cls.domain, username, 'password', None, None)
        user.set_location(cls.domain, cls.locations[location])
        return user

    @classmethod
    def make_mobile_user(cls, location):
        username = ''.join(random.sample(string.ascii_letters, 8))
        user = CommCareUser.create(cls.domain, username, 'password', None, None)
        user.set_location(cls.locations[location])
        return user

    @classmethod
    def make_form(cls, mobile_user):
        metadata = TestFormMetadata(domain=cls.domain, user_id=mobile_user._id)
        return get_simple_wrapped_form(uuid.uuid4().hex, metadata=metadata)

    @classmethod
    def extra_setup(cls):
        cls.middlesex_web_user = cls.make_web_user('Middlesex')
        cls.massachusetts_web_user = cls.make_web_user('Massachusetts')

        cambridge_user = cls.make_mobile_user('Cambridge')
        cls.cambridge_form = cls.make_form(cambridge_user)

        boston_user = cls.make_mobile_user('Boston')
        cls.boston_form = cls.make_form(boston_user)

        cls.locationless_web_user = WebUser.create(cls.domain, 'joeshmoe', 'password', None, None)
        cls.project_admin = WebUser.create(cls.domain, 'kennedy', 'password', None, None)

    @classmethod
    def extra_teardown(cls):
        delete_all_users()
        delete_all_xforms()

    def assertCanEdit(self, user, form):
        msg = "This user CANNOT edit this form!"
        self.assertTrue(can_edit_form_location(self.domain, user, form), msg=msg)

    def assertCannotEdit(self, user, form):
        msg = "This user CAN edit this form!"
        self.assertFalse(can_edit_form_location(self.domain, user, form), msg=msg)


@mock.patch('django_prbac.decorators.has_privilege', new=lambda *args, **kwargs: True)
@mock.patch('corehq.apps.users.analytics.UserES', UserESFake)
class TestAccessRestrictions(LocationHierarchyTestCase):
    domain = 'test-access-restrictions-domain'
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Brookline', []),
            ])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        super(TestAccessRestrictions, cls).setUpClass()
        cls.suffolk_user = WebUser.create(cls.domain, 'suffolk-joe', 'password', None, None)
        cls.suffolk_user.set_location(cls.domain, cls.locations['Suffolk'])
        cls.restrict_user_to_assigned_locations(cls.suffolk_user)

        def make_mobile_worker(username, location):
            worker = CommCareUser.create(cls.domain, username, '123', None, None)
            worker.set_location(cls.locations[location])
            UserESFake.save_doc(worker._doc)
            return worker

        cls.boston_worker = make_mobile_worker('boston_worker', 'Boston')
        cls.cambridge_worker = make_mobile_worker('cambridge_worker', 'Cambridge')

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.suffolk_user.delete(cls.domain, deleted_by=None)
        delete_all_users()
        super(TestAccessRestrictions, cls).tearDownClass()

    def test_can_access_location_list(self):
        self.client.login(username=self.suffolk_user.username, password="password")
        url = reverse(LocationsListView.urlname, args=[self.domain])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['locations'][0]['name'], 'Suffolk')

    def _assert_url_returns_status(self, url, status_code):
        self.client.login(username=self.suffolk_user.username, password="password")
        response = self.client.get(url)
        msg = ("This request returned a {} status code instead of the expected {}"
               .format(response.status_code, status_code))
        self.assertEqual(response.status_code, status_code, msg=msg)

    def _assert_edit_location_gives_status(self, location, status_code):
        location_id = self.locations[location].location_id
        url = reverse(EditLocationView.urlname, args=[self.domain, location_id])
        with mock.patch.object(EditLocationView, 'get', lambda *args, **kwargs: HttpResponse()):
            self._assert_url_returns_status(url, status_code)

    def test_can_edit_child_location(self):
        self._assert_edit_location_gives_status("Boston", 200)

    def test_can_edit_assigned_location(self):
        self._assert_edit_location_gives_status("Suffolk", 200)

    def test_cant_edit_parent_location(self):
        self._assert_edit_location_gives_status("Massachusetts", 403)

    def test_cant_edit_other_location(self):
        self._assert_edit_location_gives_status("Cambridge", 403)

    def test_can_edit_workers_location(self):
        self.assertTrue(
            user_views._can_edit_workers_location(
                self.suffolk_user, self.boston_worker)
        )
        self.assertFalse(
            user_views._can_edit_workers_location(
                self.suffolk_user, self.cambridge_worker)
        )

    def _assert_edit_user_gives_status(self, user, status_code):
        url = reverse(user_views.EditCommCareUserView.urlname,
                      args=[self.domain, user._id])
        with mock.patch(
            'corehq.apps.users.views.mobile.users.get_domain_languages',
            new=lambda *args: None,
        ):
            self._assert_url_returns_status(url, status_code)

    @mock.patch(
        'corehq.apps.users.views.mobile.users.get_user_location_info',
        return_value={'orphaned_case_count_per_location': {}, 'shared_locations': {}}
    )
    def test_can_edit_worker(self, _):
        self._assert_edit_user_gives_status(self.boston_worker, 200)

    def test_cant_edit_worker(self):
        self._assert_edit_user_gives_status(self.cambridge_worker, 404)

    def test_restricted_worker_list(self):
        url = reverse('paginate_mobile_workers', args=[self.domain])
        self.client.login(username=self.suffolk_user.username, password="password")

        response = self.client.get(url, content_type="application/json;charset=utf-8")

        self.assertEqual(response.status_code, 200)
        users = json.loads(response.content)['users']
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['username'], 'boston_worker')

    def test_user_can_acces_case(self):
        self.case = create_and_save_a_case(self.domain, uuid.uuid4().hex, 'test-case',
                                           owner_id=self.locations['Cambridge'].location_id)
        self.assertTrue(user_can_access_case(self.domain, self.cambridge_worker, self.case))
        self.assertFalse(user_can_access_case(self.domain, self.suffolk_user, self.case))


class TestLocationExport(LocationHierarchyTestCase):
    domain = 'test-location-export'
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['state', 'county', 'city']
    location_structure = [
        ('England', [
            ('Cambridgeshire', [
                ('Cambridge', []),  # The other Cambridge ;)
                ('Peterborough', []),
            ]),
            ('Lincolnshire', [
                ('Boston', []),  # The other Boston ;)
            ])
        ]),
        ('California', [
            ('Los Angeles', []),
        ])
    ]

    def setUp(self):
        super().setUp()
        self.user = WebUser.create(
            self.domain,
            'jbloggs',
            'Passw0rd!',
            None,
            None,
        )
        self.user.set_location(self.domain, self.locations['Cambridgeshire'])

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        super().tearDown()

    def test_location_filter_form_restricted(self):
        """
        LocationFilterForm.is_valid() returns False when a
        location-restricted user is in a separate location hierarchy
        from location_id.
        """
        self.restrict_user_to_assigned_locations(self.user)
        request_params = {
            'location_id': self.locations['California'].location_id,
            'selected_location_only': False,
            'location_status_active': LocationFilterForm.SHOW_ALL,
        }
        form = LocationFilterForm(
            request_params,
            domain=self.domain,
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        location_filters = form.get_filters()
        self.assertEqual(location_filters, {
            'location_ids': [],
            'selected_location_only': False,
        })

    def test_location_filter_form_unrestricted(self):
        """
        LocationFilterForm.is_valid() returns True when an unrestricted
        user is in a separate location hierarchy from location_id.
        """
        request_params = {
            'location_id': self.locations['California'].location_id,
            'selected_location_only': False,
            'location_status_active': LocationFilterForm.SHOW_ALL,
        }
        form = LocationFilterForm(
            request_params,
            domain=self.domain,
            user=self.user,
        )
        self.assertTrue(form.is_valid())
        location_filters = form.get_filters()
        self.assertEqual(location_filters, {
            'location_ids': [self.locations['California'].location_id],
            'selected_location_only': False,
        })
