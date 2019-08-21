from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.urls import reverse
from django.test import Client, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.exceptions import LocationConsistencyError
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.views import LocationTypesView
from corehq.apps.users.models import WebUser
from django.contrib.messages import get_messages
import mock


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
}


class LocationTypesViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(LocationTypesViewTest, cls).setUpClass()
        cls.domain = "test-domain"
        cls.project = create_domain(cls.domain)
        cls.couch_user = WebUser.create(cls.domain, "test", "foobar")
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
        cls.couch_user.delete()
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
