from __future__ import absolute_import
from __future__ import unicode_literals

from ..resources.v0_1 import _user_locations_ids
from .util import LocationHierarchyTestCase
from corehq.apps.users.models import WebUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
import six


class BaseTestLocationQuerysetMethods(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ]),
        ('California', [
            ('Los Angeles', []),
        ])
    ]


class TestApiUtils(BaseTestLocationQuerysetMethods):

    @classmethod
    def setUpClass(cls):
        super(TestApiUtils, cls).setUpClass()
        delete_all_users()

    def setUp(self):
        super(TestApiUtils, self).setUp()
        self.web_user = WebUser.create(self.domain, 'blah', 'password')

    def tearDown(self):
        delete_all_users()
        super(TestApiUtils, self).tearDown()

    def test_restricted_user_locations_ids(self):
        user = self.web_user
        user.set_location(self.domain, self.locations['Middlesex'])
        self.restrict_user_to_assigned_locations(user)
        project = self.domain_obj
        result = _user_locations_ids(user, project, only_editable=False)
        self.assertTrue(isinstance(result, list), result)
        self.assertTrue(
            all(isinstance(it, six.text_type) for it in result),
            result,
        )
