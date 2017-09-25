from base64 import b64encode

import mock

from corehq.apps.export.models import FormExportInstance
from corehq.apps.users.models import WebUser
from corehq.apps.locations.tests.util import LocationHierarchyTestCase


USERNAME = 'polly'
PASSWORD = 'the_fjords'


@mock.patch('corehq.apps.locations.permissions.notify_exception', new=mock.MagicMock())
@mock.patch('corehq.apps.export.views.domain_has_privilege', new=lambda x, y: True)  # All of the things!
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

        self.export = FormExportInstance(
            domain=self.domain,
            export_format='html',
        )
        self.export.save()

    def tearDown(self):
        self.export.delete()
        WebUser.get_by_username(USERNAME).delete()

    def test_request_403(self):
        """
        Check that the user gets location_restricted_response
        """
        extra = {'HTTP_AUTHORIZATION': 'basic ' + b64encode(':'.join((USERNAME, PASSWORD)))}
        excel_dashboard_url = '/a/petshop/data/export/custom/dailysaved/download/{}/'.format(self.export.get_id)
        response = self.client.get(excel_dashboard_url, **extra)
        self.assertEqual(response.status_code, 403)
