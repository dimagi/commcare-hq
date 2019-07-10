from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch, MagicMock
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from ..models import SQLLocation, LocationType
from ..forms import LocationFormSet
from .util import setup_locations_and_types


@patch('corehq.apps.locations.tasks._get_users_by_loc_id')
class TestChangeHasUser(TestCase):
    domain = 'test-has-user'
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ])
    ]

    def setUp(self):
        self.domain_obj = create_domain(self.domain)

        self.location_types, self.locations = setup_locations_and_types(
            self.domain,
            self.location_type_names,
            self.stock_tracking_types,
            self.location_structure,
        )

    def tearDown(self):
        self.domain_obj.delete()

    def assertUserState(self, active, inactive):
        """active and inactive should be lists of usernames"""
        for usernames, is_active in [(active, True), (inactive, False)]:
            self.assertItemsEqual(
                usernames,
                [user.raw_username for user in
                 CommCareUser.by_domain(self.domain, is_active=is_active)]
            )

    def submit_form(self, name):
        form_data = {
            'name': name,
            'location_type': 'county',
            'location_user-username': name.lower(),
            'location_user-new_password': '123',
            'location_user-first_name': '',
            'location_user-last_name': '',
        }
        form = LocationFormSet(
            location=SQLLocation(domain=self.domain, parent=self.locations['Massachusetts']),
            bound_data=form_data,
            request_user=MagicMock(),
            is_new=True,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

    def test(self, existing_users_mock):
        # starting off, no users
        self.assertUserState(active=[], inactive=[])

        # turning it on should make users for the existing counties
        existing_users_mock.return_value = {}
        county = self.location_types['county']
        county.has_user = True
        county.save()
        self.assertUserState(active=['middlesex', 'suffolk'], inactive=[])

        # add a location, it should auto create a user
        self.submit_form('Essex')
        self.assertUserState(active=['middlesex', 'suffolk', 'essex'], inactive=[])

        # turning it off should inactivate location users
        county = LocationType.objects.get(pk=county.pk)
        county.has_user = False
        county.save()
        self.assertUserState(active=[], inactive=['middlesex', 'suffolk', 'essex'])

        # add a location, it shouldn't create a user
        self.submit_form('Worcester')
        self.assertUserState(active=[], inactive=['middlesex', 'suffolk', 'essex'])

        # turning it back on should reactivate the previous users and create a
        # new user for Worcester
        existing_users_mock.return_value = {
            user.user_location_id: user for user in
            CommCareUser.by_domain(self.domain, is_active=False)
        }
        county = self.location_types['county']
        county.has_user = True
        county.save()
        self.assertUserState(active=['middlesex', 'suffolk', 'essex', 'worcester'], inactive=[])
