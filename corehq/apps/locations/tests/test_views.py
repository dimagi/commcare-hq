import json
import uuid

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from unittest import mock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.exceptions import LocationConsistencyError
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.views import LocationTypesView
from corehq.apps.users.models import WebUser, CommCareUser

OTHER_DETAILS = {
    'expand_from': None,
    'expand_to': None,
    'expand_from_root': False,
    'include_without_expanding': None,
    'include_only': [],
    'parent_type': '',
    'administrative': '',
    'shares_cases': False,
    'view_descendants': False,
    'expand_view_child_data_to': None,
}


class LocationTypesViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(LocationTypesViewTest, cls).setUpClass()
        cls.domain = "test-domain"
        cls.project = create_domain(cls.domain)
        cls.couch_user = WebUser.create(cls.domain, "test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain, is_admin=True)
        cls.couch_user.set_role(cls.domain, "admin")
        cls.couch_user.save()
        cls.loc_type1 = LocationType(domain=cls.domain, name='type1', code='code1')
        cls.loc_type1.save()
        cls.loc_type2 = LocationType(domain=cls.domain, name='type2', code='code2')
        cls.loc_type2.save()

    def setUp(self):
        self.url = reverse(LocationTypesView.urlname, args=[self.domain])
        self.client = Client()
        self.client.login(username='test', password='foobar')

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete(cls.domain, deleted_by=None)
        cls.project.delete()
        super(LocationTypesViewTest, cls).tearDownClass()

    @mock.patch('django_prbac.decorators.has_privilege', return_value=True)
    def send_request(self, data, _):
        return self.client.post(self.url, {'json': json.dumps(data)})

    def test_missing_property(self):
        with self.assertRaises(LocationConsistencyError):
            self.send_request({'loc_types': [{}]})

    def test_swap_name(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': self.loc_type2.name, 'pk': self.loc_type1.pk})
        loc_type2.update({'name': self.loc_type1.name, 'pk': self.loc_type2.pk})
        data = {'loc_types': [loc_type1, loc_type2]}
        response = self.send_request(data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            str(messages[0].message),
            'Looks like you are assigning a location name/code to a different location in the same request. '
            'Please do this in two separate updates by using a temporary name to free up the name/code to be '
            're-assigned.'
        )

    def test_swap_code(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': self.loc_type1.name, 'pk': self.loc_type1.pk, 'code': self.loc_type2.code})
        loc_type2.update({'name': self.loc_type2.name, 'pk': self.loc_type2.pk, 'code': self.loc_type1.code})
        data = {'loc_types': [loc_type1, loc_type2]}
        response = self.send_request(data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(
            str(messages[0].message),
            'Looks like you are assigning a location name/code to a different location in the same request. '
            'Please do this in two separate updates by using a temporary name to free up the name/code to be '
            're-assigned.'
        )

    def test_valid_update(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': "new name", 'pk': self.loc_type1.pk, 'code': self.loc_type1.code})
        loc_type2.update({'name': "new name 2", 'pk': self.loc_type2.pk, 'code': self.loc_type2.code})
        data = {'loc_types': [loc_type1, loc_type2]}
        response = self.send_request(data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)

    def test_hierarchy(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': "new name", 'pk': self.loc_type1.pk, 'code': self.loc_type1.code})
        loc_type2.update({'name': "new name 2", 'pk': self.loc_type2.pk, 'parent_type': self.loc_type1.pk,
                          'code': self.loc_type2.code})
        data = {'loc_types': [loc_type1, loc_type2]}
        response = self.send_request(data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)

    def test_child_data(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': "new name", 'pk': self.loc_type1.pk,
                          'view_descendants': True, 'expand_view_child_data_to': self.loc_type2.pk,
                          'code': self.loc_type1.code})
        loc_type2.update({'name': "new name 2", 'pk': self.loc_type2.pk, 'parent_type': self.loc_type1.pk,
                          'code': self.loc_type2.code})
        data = {'loc_types': [loc_type1, loc_type2]}
        response = self.send_request(data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)

    def test_invalid_child_data(self):
        loc_type1 = OTHER_DETAILS.copy()
        loc_type2 = OTHER_DETAILS.copy()
        loc_type1.update({'name': "new name", 'pk': self.loc_type1.pk, 'code': self.loc_type1.code})
        loc_type2.update({'name': "new name 2", 'pk': self.loc_type2.pk, 'parent_type': self.loc_type1.pk,
                          'view_descendants': True, 'expand_view_child_data_to': self.loc_type1.pk,
                          'code': self.loc_type2.code})
        data = {'loc_types': [loc_type1, loc_type2]}
        with self.assertRaises(LocationConsistencyError):
            self.send_request(data)


@es_test(requires=[user_adapter], setup_class=True)
class GetAssignedLocationNamesForUserTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.loc_type = LocationType.objects.create(
            domain=cls.domain, name='Middle Earth',
        )
        cls.locations = [
            SQLLocation.objects.create(
                domain=cls.domain,
                name='Shire',
                location_id=str(uuid.uuid4().hex),
                location_type=cls.loc_type,
            ),
            SQLLocation.objects.create(
                domain=cls.domain,
                name='Gondor',
                location_id=str(uuid.uuid4().hex),
                location_type=cls.loc_type,
            ),
            SQLLocation.objects.create(
                domain=cls.domain,
                name='Rivendell',
                location_id=str(uuid.uuid4().hex),
                location_type=cls.loc_type,
            ),
        ]

        cls.web_user = WebUser.create(
            cls.domain,
            username='test',
            password='123',
            created_by=None,
            created_via=None,
        )
        cls.user = CommCareUser.create(
            cls.domain,
            username='foobar',
            password='123',
            created_by=None,
            created_via=None,
            email='foobar@email.com',
            location=cls.locations[0],
        )
        cls.user.set_location(cls.locations[1])
        user_adapter.bulk_index([cls.web_user, cls.user], refresh=True)

    def setUp(self):
        self.url = reverse('get_assigned_location_names_for_user', args=[self.domain])
        self.client = Client()
        self.client.login(username='test', password='123')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, None)
        cls.web_user.delete(cls.domain, deleted_by=None)
        for loc in cls.locations:
            loc.delete()
        cls.loc_type.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    def _send_request(self, user_id=None):
        data = {}
        if user_id:
            data['user_id'] = user_id
        return self.client.get(self.url, data)

    def test_no_or_invalid_user_id(self):
        response = self._send_request()
        self.assertEqual(response.status_code, 404)
        response = self._send_request('abc')
        self.assertEqual(response.status_code, 404)

    def test_get_location_names(self):
        response = self._send_request(self.user.user_id)
        self.assertEqual(response.status_code, 200)
        expected_data = {
            'assigned_location_names_html': '<div>Shire, <strong>Gondor</strong></div>',
        }
        self.assertEqual(response.json(), expected_data)

    def test_user_has_no_locations(self):
        response = self._send_request(self.web_user.user_id)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json['assigned_location_names_html'], '<div></div>')
