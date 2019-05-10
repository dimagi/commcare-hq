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
@mock.patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
@mock.patch('corehq.apps.analytics.tasks._track_on_hubspot')
class TestSendToHubspot(TestCase):
    domain = 'test-send-to-hubspot'

    def test_registration(
            self,
            _track_on_hubspot,
            _get_user_hubspot_id,
            _send_hubspot_form_request,
    ):
        request = self.get_request()

        # The is present in hubspot by the time this is called
        _get_user_hubspot_id.return_value = "123abc"

        buyer_props = {'buyer_persona': 'Old-Timey Prospector'}
        track_web_user_registration_hubspot(request, self.user, buyer_props)

        self.assert_signup_form_submitted(_send_hubspot_form_request)
        self.assert_properties_sent(_track_on_hubspot, buyer_props)

    def test_registration_no_user_hubspot_id(
            self,
            _track_on_hubspot,
            _get_user_hubspot_id,
            _send_hubspot_form_request,
    ):
        request = self.get_request()

        # The user isn't present in hubspot
        _get_user_hubspot_id.return_value = ""

        buyer_props = {'buyer_persona': 'Old-Timey Prospector'}
        track_web_user_registration_hubspot(request, self.user, buyer_props)

        self.assert_signup_form_submitted(_send_hubspot_form_request)
        # Since the user ID wasn't found,t he properties were never submitted
        _track_on_hubspot.assert_not_called()

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

    def assert_signup_form_submitted(self, _send_hubspot_form_request):
        _send_hubspot_form_request.assert_called_once()
        url, data = _send_hubspot_form_request.call_args[0]
        self.assertIn(HUBSPOT_SIGNUP_FORM_ID, url)

    def assert_properties_sent(self, _track_on_hubspot, buyer_props):
        _track_on_hubspot.assert_called_once()
        webuser, properties = _track_on_hubspot.call_args[0]
        self.assertDictContainsSubset(buyer_props, properties)
