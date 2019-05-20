from __future__ import absolute_import, unicode_literals

from django.test import RequestFactory, TestCase, override_settings

import mock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..tasks import (
    HUBSPOT_COOKIE,
    HUBSPOT_SIGNUP_FORM_ID,
    track_web_user_registration_hubspot,
)


@override_settings(ANALYTICS_IDS={'HUBSPOT_API_ID': '1234'})
@mock.patch('corehq.apps.analytics.tasks.requests.get', mock.MagicMock())
@mock.patch('corehq.apps.analytics.tasks.requests.post', mock.MagicMock())
@mock.patch('corehq.apps.analytics.tasks._send_hubspot_form_request')
class TestSendToHubspot(TestCase):
    domain = 'test-send-to-hubspot'

    def test_registration(self, _send_hubspot_form_request):
        request = self.get_request()
        buyer_props = {'buyer_persona': 'Old-Timey Prospector'}
        track_web_user_registration_hubspot(request, self.user, buyer_props)

        _send_hubspot_form_request.assert_called_once()
        hubspot_id, form_id, data = _send_hubspot_form_request.call_args[0]
        self.assertEqual(form_id, HUBSPOT_SIGNUP_FORM_ID)
        self.assertDictContainsSubset(buyer_props, data)

    @classmethod
    def setUpClass(cls):
        super(TestSendToHubspot, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(cls.domain, "seamus@example.com", "*****")
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.user.delete()
        super(TestSendToHubspot, cls).tearDownClass()

    def get_request(self):
        request = RequestFactory().request()
        request.couch_user = self.user
        request.domain = self.domain
        # The hubspot cookie must be passed from the client
        request.COOKIES[HUBSPOT_COOKIE] = '54321'
        return request
