from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid
import random
import string
from io import BytesIO
import mock

from django.urls import reverse
from django.http import HttpResponse

from corehq.apps.es.fake.users_fake import UserESFake
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.toggles import (RESTRICT_FORM_EDIT_BY_LOCATION, NAMESPACE_DOMAIN)
from corehq.apps.users.views.mobile import users as user_views
from corehq.form_processor.utils.xform import (
    TestFormMetadata,
    get_simple_wrapped_form,
)
from corehq.form_processor.tests.utils import run_with_all_backends
from casexml.apps.case.tests.util import delete_all_xforms

from corehq.util.test_utils import create_and_save_a_case
from ..views import LocationsListView, EditLocationView
from ..permissions import can_edit_form_location, user_can_access_case
from .util import LocationHierarchyTestCase


class FormEditRestrictionsMixin(object):
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

    @run_with_all_backends
    def test_can_edit_form_in_county(self):
        self.assertCanEdit(self.middlesex_web_user, self.cambridge_form)

    @run_with_all_backends
    def test_cant_edit_out_of_county(self):
        self.assertCannotEdit(self.middlesex_web_user, self.boston_form)

    @run_with_all_backends
    def test_can_edit_any_form(self):
        self.assertCanEdit(self.massachusetts_web_user, self.cambridge_form)
        self.assertCanEdit(self.massachusetts_web_user, self.boston_form)

    @run_with_all_backends
    def test_project_admin_can_edit_anything(self):
        self.project_admin.get_domain_membership(self.domain).is_admin = True
        self.project_admin.save()

        self.assertCanEdit(self.project_admin, self.cambridge_form)
        self.assertCanEdit(self.project_admin, self.boston_form)

    @run_with_all_backends
    def test_unassigned_web_user_cant_edit_anything(self):
        self.assertCannotEdit(self.locationless_web_user, self.cambridge_form)
        self.assertCannotEdit(self.locationless_web_user, self.boston_form)

    #### The rest of this class is helper methods and setup ####

    @classmethod
    def make_web_user(cls, location):
        username = ''.join(random.sample(string.letters, 8))
        user = WebUser.create(cls.domain, username, 'password')
        user.set_location(cls.domain, cls.locations[location])
        return user

    @classmethod
    def make_mobile_user(cls, location):
        username = ''.join(random.sample(string.letters, 8))
        user = CommCareUser.create(cls.domain, username, 'password')
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

        cls.locationless_web_user = WebUser.create(cls.domain, 'joeshmoe', 'password')
        cls.project_admin = WebUser.create(cls.domain, 'kennedy', 'password')

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


class TestDeprecatedFormEditRestrictions(FormEditRestrictionsMixin, LocationHierarchyTestCase):
    """This class mostly just tests the RESTRICT_FORM_EDIT_BY_LOCATION feature flag"""
    domain = 'TestDeprecatedFormEditRestrictions-domain'

    @classmethod
    def setUpClass(cls):
        super(TestDeprecatedFormEditRestrictions, cls).setUpClass()
        cls.extra_setup()
        # enable flag
        RESTRICT_FORM_EDIT_BY_LOCATION.set(cls.domain, True, NAMESPACE_DOMAIN)
        # check checkbox
        cls.domain_obj.location_restriction_for_users = True
        cls.domain_obj.save()

    @classmethod
    def tearDownClass(cls):
        cls.extra_teardown()
        super(TestDeprecatedFormEditRestrictions, cls).tearDownClass()


class TestNewFormEditRestrictions(FormEditRestrictionsMixin, LocationHierarchyTestCase):
    """Tests the new way of doing location-based restrictions.
    TODO: reconcile with the Mixin after removing the old permissions"""
    domain = 'TestNewFormEditRestrictions-domain'

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

    # TODO add more tests, maybe with cls.project_admin?


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
        cls.suffolk_user = WebUser.create(cls.domain, 'suffolk-joe', 'password')
        cls.suffolk_user.set_location(cls.domain, cls.locations['Suffolk'])
        cls.restrict_user_to_assigned_locations(cls.suffolk_user)

        def make_mobile_worker(username, location):
            worker = CommCareUser.create(cls.domain, username, '123')
            worker.set_location(cls.locations[location])
            UserESFake.save_doc(worker._doc)
            return worker

        cls.boston_worker = make_mobile_worker('boston_worker', 'Boston')
        cls.cambridge_worker = make_mobile_worker('cambridge_worker', 'Cambridge')

    @classmethod
    def tearDownClass(cls):
        UserESFake.reset_docs()
        cls.suffolk_user.delete()
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
        noop = lambda *args, **kwargs: HttpResponse()
        with mock.patch.object(EditLocationView, 'get', noop):
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

    def test_can_edit_worker(self):
        self._assert_edit_user_gives_status(self.boston_worker, 200)

    def test_cant_edit_worker(self):
        self._assert_edit_user_gives_status(self.cambridge_worker, 404)

    def _call_djangoRMI(self, url, method_name, data):
        data = json.dumps(data)
        return self.client.post(
            url,
            content_type="application/json;charset=utf-8",
            **{
                'HTTP_DJNG_REMOTE_METHOD': method_name,
                'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest',
                'CONTENT_LENGTH': len(data),
                'wsgi.input': BytesIO(data),
            })

    def test_restricted_worker_list(self):
        url = reverse(user_views.MobileWorkerListView.urlname, args=[self.domain])
        self.client.login(username=self.suffolk_user.username, password="password")

        # This is how you test a djangoRMI method...
        response = self._call_djangoRMI(url, 'get_pagination_data', data={
            "limit": 10,
            "page": 1,
            "customFormFieldNames": [],
            "showDeactivatedUsers": False
        })

        self.assertEqual(response.status_code, 200)
        users = json.loads(response.content)['response']['itemList']
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['username'], 'boston_worker')

    def test_user_can_acces_case(self):
        self.case = create_and_save_a_case(self.domain, uuid.uuid4().hex, 'test-case',
                                           owner_id=self.locations['Cambridge'].location_id)
        self.assertTrue(user_can_access_case(self.domain, self.cambridge_worker, self.case))
        self.assertFalse(user_can_access_case(self.domain, self.suffolk_user, self.case))
