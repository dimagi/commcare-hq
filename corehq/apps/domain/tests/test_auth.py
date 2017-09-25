from base64 import b64encode
from django.http import HttpResponse
from mock import Mock
from corehq.apps.domain.decorators import basic_auth
from corehq.apps.locations.permissions import location_safe
from corehq.apps.users.models import WebUser
from corehq.apps.locations.tests.util import LocationHierarchyTestCase


USERNAME = 'polly'
PASSWORD = 'the_fjords'


@basic_auth
@location_safe
def some_view(request, domain):
    return HttpResponse('Hello Polly!', content_type='text/plain')


class BasicAuthTest(LocationHierarchyTestCase):
    domain = 'petshop'
    location_type_names = ['city']
    location_structure = [
        ('London', []),
        ('Oslo', []),
    ]

    def setUp(self):
        user = WebUser.create(self.domain, USERNAME, PASSWORD)
        user.eula.signed = True
        user.save()
        user.set_location(self.domain, self.locations['London'])
        self.restrict_user_to_assigned_locations(user)

    def tearDown(self):
        WebUser.get_by_username(USERNAME).delete()

    def test_basic_auth(self):
        request = Mock()
        request.META = {
            'HTTP_AUTHORIZATION': 'basic ' + b64encode(':'.join((USERNAME, PASSWORD)))
        }
        request.domain = self.domain
        response = some_view(request, self.domain)
        self.assertTrue(some_view.is_location_safe)
        self.assertFalse(request.can_access_all_locations)
        self.assertEqual(response.status_code, 200)
