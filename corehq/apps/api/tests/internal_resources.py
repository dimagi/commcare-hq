from corehq.apps.fixtures.resources.v0_1 import InternalFixtureResource
from corehq.apps.locations.resources.v0_1 import InternalLocationResource

from .utils import APIResourceTest


class InternalTestMixin(object):
    def assert_accessible_via_sessions(self, url):
        # api auth should succeed
        headers = self._get_api_key_auth_headers()
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
        # session auth should also succeed since these are used internally over sessions
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class InternalFixtureResourceTest(APIResourceTest, InternalTestMixin):
    resource = InternalFixtureResource
    api_name = 'v0_5'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)


class InternalLocationResourceTest(APIResourceTest, InternalTestMixin):
    resource = InternalLocationResource
    api_name = 'v0_5'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)
