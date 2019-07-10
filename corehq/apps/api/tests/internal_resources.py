from __future__ import absolute_import, unicode_literals

from corehq.apps.fixtures.resources.v0_1 import InternalFixtureResource
from corehq.apps.locations.resources.v0_1 import InternalLocationResource
from custom.ewsghana.resources.v0_1 import EWSLocationResource

from .utils import APIResourceTest


class InternalTestMixin(object):
    def assert_accessible_via_sessions(self, url):
        # api auth should succeed
        api_url = self._api_url(url, self.username)
        response = self.client.get(api_url)
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


class EWSLocationResourceTest(APIResourceTest, InternalTestMixin):
    resource = EWSLocationResource
    api_name = 'v0_3'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)
