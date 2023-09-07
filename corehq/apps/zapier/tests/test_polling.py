import json
from datetime import datetime
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth.models import User

from corehq import privileges
from corehq.apps.api import resources
from corehq.apps.api.resources import v0_4
from corehq.apps.app_manager.models import Application
from corehq.apps.api.models import ESXFormInstance

from corehq.apps.zapier.api.v0_5 import ZapierApplicationResource, ZapierXFormInstanceResource
from corehq.util.test_utils import flag_enabled


@flag_enabled('API_THROTTLE_WHITELIST')
class XFormPollingTests(SimpleTestCase):
    def test_can_poll_with_only_zapier_privilege(self):
        self.forms = [self._create_form(id='7', domain='test-domain')]
        self.domain_privileges = [privileges.ZAPIER_INTEGRATION]
        request = self._create_request('test@test.com', 'test-domain', api_key='121212')

        result = self.resource.dispatch('list', request,
            domain='test-domain', api_name='v0.5', resource_name='form')
        rows_found = json.loads(result.content.decode('utf8'))['meta']['total_count']
        self.assertEqual(rows_found, 1)

    def setUp(self):
        self.resource = ZapierXFormInstanceResource()

        self.domain_privileges = [privileges.ZAPIER_INTEGRATION]
        self.forms = []

        resource_patcher = patch.object(self.resource, 'obj_get_list', side_effect=self._mock_get_forms)
        resource_patcher.start()
        self.addCleanup(resource_patcher.stop)

        domain_privilege_patcher = patch.object(
            resources, 'domain_has_privilege', side_effect=self._mock_domain_has_privilege)
        domain_privilege_patcher.start()
        self.addCleanup(domain_privilege_patcher.stop)

        workflow_patcher = patch.object(resources, 'track_workflow')
        workflow_patcher.start()
        self.addCleanup(workflow_patcher.stop)

        #####
        # Tastypie mocks
        auth_patcher = patch.object(self.resource._meta.authentication, 'is_authenticated', return_value=True)
        auth_patcher.start()
        self.addCleanup(auth_patcher.stop)

        accessed_patcher = patch.object(self.resource._meta.throttle, 'accessed', return_value=None)
        accessed_patcher.start()
        self.addCleanup(accessed_patcher.stop)
        #####

    def _create_form(self, id, domain='test-domain'):
        return ESXFormInstance({
            '_id': id,
            'domain': domain,
            'received_on': 'x',
            'inserted_at': 'x',
            'form': {
                'some_data': 'test'
            }
        })

    def _create_request(self, username, domain, api_key):
        user = User(username=username)
        request = RequestFactory().get('url', username=username, api_key=api_key)
        request.user = request.couch_user = user
        request.domain = domain

        return request

    def _mock_domain_has_privilege(self, domain, privilege):
        return privilege in self.domain_privileges

    def _mock_get_forms(self, *args, **kwargs):
        return self.forms


@flag_enabled('API_THROTTLE_WHITELIST')
class ApplicationPollingTests(SimpleTestCase):
    def test_can_poll_with_only_zapier_privilege(self):
        self.applications = [self._create_app('1'), self._create_app('2')]
        self.domain_privileges = [privileges.ZAPIER_INTEGRATION]
        request = self._create_request('test@test.com', 'test-domain', api_key='121212')

        result = self.resource.dispatch('list', request,
            domain='test-domain', api_name='v0.5', resource_name='application')
        rows_found = json.loads(result.content.decode('utf8'))['meta']['total_count']
        self.assertEqual(rows_found, 2)

    def setUp(self):
        self.resource = ZapierApplicationResource()
        self.domain_privileges = [privileges.ZAPIER_INTEGRATION]
        self.applications = []

        apps_patcher = patch.object(v0_4, 'get_apps_in_domain', side_effect=self._mock_get_applications)
        apps_patcher.start()
        self.addCleanup(apps_patcher.stop)

        domain_privilege_patcher = patch.object(
            resources, 'domain_has_privilege', side_effect=self._mock_domain_has_privilege)
        domain_privilege_patcher.start()
        self.addCleanup(domain_privilege_patcher.stop)

        workflow_patcher = patch.object(resources, 'track_workflow')
        workflow_patcher.start()
        self.addCleanup(workflow_patcher.stop)

        #####
        # Tastypie mocks
        auth_patcher = patch.object(self.resource._meta.authentication, 'is_authenticated', return_value=True)
        auth_patcher.start()
        self.addCleanup(auth_patcher.stop)

        accessed_patcher = patch.object(self.resource._meta.throttle, 'accessed', return_value=None)
        accessed_patcher.start()
        self.addCleanup(accessed_patcher.stop)
        #####

    def _create_request(self, username, domain, api_key):
        user = User(username=username)
        request = RequestFactory().get('url', username=username, api_key=api_key)
        request.user = request.couch_user = user
        request.domain = domain

        return request

    def _create_app(self, id, name='test'):
        return Application(_id=id, name=name, date_created=datetime.now())

    def _mock_domain_has_privilege(self, domain, privilege):
        return privilege in self.domain_privileges

    def _mock_get_applications(self, *args, **kwargs):
        return self.applications
